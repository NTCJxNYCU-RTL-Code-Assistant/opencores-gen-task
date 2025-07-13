#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenCores 爬蟲程式 - 使用 Selenium 登入並下載項目文件
"""

import requests
import time
import os
import json
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin, urlparse
import logging
from pathlib import Path
import re
from typing import List, Dict, Optional, TypedDict, Literal
import argparse
import tarfile
import shutil

# Selenium 相關導入
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement
from webdriver_manager.chrome import ChromeDriverManager

# 設定日誌
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler('opencores_crawler.log',
                                            encoding='utf-8'),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)


class Project(TypedDict):
    category: str
    name: str
    title: str
    url: str
    file_state: Literal['yes', 'no', 'external']
    tags: List[str]
    info: Optional[Dict]


class OpenCoresCrawler:

    def __init__(self,
                 download_dir: str = "downloads",
                 headless: bool = False):
        """
        初始化 OpenCores 爬蟲
        
        Args:
            download_dir: 下載目錄
            headless: 是否使用無頭模式
        """
        self.base_url = "https://opencores.org"
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)

        # 設置 Chrome 選項
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )

        # 初始化 WebDriver
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service,
                                           options=chrome_options)
            self.driver.implicitly_wait(10)
            logger.info("Chrome WebDriver 初始化成功")
        except Exception as e:
            logger.error(f"WebDriver 初始化失敗: {e}")
            raise

        # 用於下載文件的 requests session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

        # 儲存已處理的項目
        self.processed_projects = set()
        for f in os.listdir(download_dir):
            # 如果 f 是資料夾且裡面有檔案，才視為已處理過
            full_path = os.path.join(download_dir, f)
            if os.path.isdir(full_path):
                if os.listdir(full_path):  # 資料夾內有檔案
                    self.processed_projects.add(f)
        logger.info(f"已處理項目: {len(self.processed_projects)}")
        self.failed_downloads = []

    def __del__(self):
        """清理資源"""
        if hasattr(self, 'driver'):
            self.driver.quit()

    def login(self, username: str, password: str) -> bool:
        """
        登入 OpenCores 網站
        
        Args:
            username: 用戶名
            password: 密碼
            
        Returns:
            bool: 登入是否成功
        """
        try:
            # 訪問首頁
            logger.info("正在訪問 OpenCores 首頁...")
            self.driver.get(self.base_url)

            # 等待頁面加載
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "form")))

            # 查找登入表單元素
            try:
                username_input = self.driver.find_element(By.NAME, "user")
                password_input = self.driver.find_element(By.NAME, "pass")
                remember_checkbox = self.driver.find_element(
                    By.NAME, "remember")
                submit_button = self.driver.find_element(
                    By.CSS_SELECTOR, "input[type='submit'][value='Login']")

                # 填寫登入資訊
                username_input.clear()
                username_input.send_keys(username)

                password_input.clear()
                password_input.send_keys(password)

                # 勾選記住我
                if not remember_checkbox.is_selected():
                    remember_checkbox.click()

                # 提交表單
                submit_button.click()

                # 等待頁面跳轉
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body")))

                # 檢查登入是否成功 - 查找 "My account" 連結
                if self.test_login_status():
                    logger.info("登入成功")

                    # 同步 cookies 到 requests session
                    for cookie in self.driver.get_cookies():
                        self.session.cookies.set(cookie['name'],
                                                 cookie['value'])

                    return True
                else:
                    logger.error("登入失敗")
                    return False

            except NoSuchElementException as e:
                logger.error(f"找不到登入表單元素: {e}")
                return False

        except Exception as e:
            logger.error(f"登入過程中出現錯誤: {e}")
            return False

    def test_login_status(self) -> bool:
        """
        測試登入狀態是否有效
        
        Returns:
            bool: 登入狀態是否有效
        """
        try:
            # 檢查當前頁面是否存在 "My account" 連結
            try:
                self.driver.find_element(By.CSS_SELECTOR, 'a[href="/profile"]')
                logger.info("登入狀態測試：已登入 (找到 My account 連結)")
                return True
            except NoSuchElementException:
                logger.info("登入狀態測試：未登入 (未找到 My account 連結)")
                return False

        except Exception as e:
            logger.error(f"測試登入狀態時出錯: {e}")
            return False

    def get_project_list(self) -> List[Project]:
        """
        獲取所有項目列表
        
        Returns:
            List[Project]: 項目列表
        """
        projects = []

        try:
            # 訪問項目頁面
            projects_url = f"{self.base_url}/projects"
            logger.info(f"正在訪問項目頁面: {projects_url}")
            self.driver.get(projects_url)

            # 等待頁面初始載入
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body")))

            # 額外等待確保動態內容載入開始
            time.sleep(3)

            # 等待項目連結載入完成
            logger.info("等待項目列表載入完成...")

            WebDriverWait(self.driver,
                          300).until(lambda driver: driver.execute_script(
                              "return document.readyState") == "complete")

            # 額外等待確保動態內容載入完成
            time.sleep(3)

            # 展開所有分類
            self._expand_all_categories_()

            # 等待項目列表載入完成
            time.sleep(3)

            # 收集所有項目
            projects = self._collect_all_projects()

            logger.info(f"總共找到 {len(projects)} 個項目")
            return projects

        except Exception as e:
            logger.error(f"獲取項目列表時出錯: {e}")
            return []

    def _get_categories_info(self) -> List[Dict]:
        """
        獲取所有分類的信息
        
        Returns:
            List[Dict]: 分類信息列表
        """
        categories = []

        try:
            # 查找所有分類標題（h1 且內容含有 span.toggle）
            category_headers = self.driver.find_elements(
                By.CSS_SELECTOR, 'h1:has(span.toggle)')

            for header in category_headers:
                try:
                    # 提取分類名稱和數量
                    title_span = header.find_element(By.CSS_SELECTOR,
                                                     'span.title')
                    title_text = title_span.text

                    # 分離名稱和數量
                    count_span = title_span.find_element(
                        By.CSS_SELECTOR, 'span.count')
                    count_text = count_span.text
                    category_name = title_text.replace(count_text, '').strip()

                    categories.append({
                        'name': category_name,
                        'count': count_text,
                        'element': header
                    })

                    print(f"分類: {category_name}, 數量: {count_text}")

                except Exception as e:
                    logger.warning(f"解析分類標題時出錯: {e}")
                    continue

            print(f"\n總共找到 {len(categories)} 個分類")
            return categories

        except Exception as e:
            logger.error(f"獲取分類信息時出錯: {e}")
            return []

    def _expand_all_categories_(self) -> None:
        """
        展開所有分類
        """
        try:
            # 查找所有可點擊的分類標題
            category_headers = self.driver.find_elements(
                By.CSS_SELECTOR, 'h1:has(span.toggle)')

            for i, header in enumerate(category_headers):
                try:
                    # 滾動到元素可見
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView(true);", header)
                    time.sleep(0.5)

                    # 點擊分類標題來展開
                    header.click()
                    logger.info(f"展開第 {i+1} 個分類")

                    # 等待內容載入
                    time.sleep(1)

                except Exception as e:
                    logger.warning(f"展開第 {i+1} 個分類時出錯: {e}")
                    continue

            logger.info("所有分類展開完成")

        except Exception as e:
            logger.error(f"展開分類時出錯: {e}")

    def _collect_all_projects(self) -> List[Project]:
        """
        收集所有展開後的項目
        
        Returns:
            List[Project]: 項目列表
        """
        projects: List[Project] = []

        try:
            logger.info("=== 收集項目資訊 ===")

            category_headers = self.driver.find_elements(
                By.CSS_SELECTOR, 'h1:has(span.toggle)')

            for header in category_headers:
                try:
                    # 獲取分類名稱
                    title_span = header.find_element(By.CSS_SELECTOR,
                                                     'span.title')
                    title_text = title_span.text
                    count_span = title_span.find_element(
                        By.CSS_SELECTOR, 'span.count')
                    count_text = count_span.text
                    category_name = title_text.replace(count_text, '').strip()

                    logger.info(f"正在處理分類: {category_name}")

                    # 查找該分類下的表格
                    tables = header.find_elements(By.XPATH,
                                                  'following-sibling::table')

                    if tables:
                        table = tables[0]  # 取第一個表格

                        # 查找表格中的所有項目行
                        rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')

                        logger.info(f"找到 {len(rows)} 個項目")

                        for row in rows:
                            try:
                                # 提取項目資訊
                                project_info = self._extract_project_info(
                                    row, category_name)
                                if project_info:
                                    projects.append(project_info)

                            except Exception as e:
                                logger.warning(f"處理項目行時出錯: {e}")
                                continue

                except Exception as e:
                    logger.warning(
                        f"處理分類 {category_name if 'category_name' in locals() else 'unknown'} 時出錯: {e}"
                    )
                    continue

            # 去重（避免重複項目）
            unique_projects = []
            seen_names = set()

            for project in projects:
                if project['name'] not in seen_names:
                    unique_projects.append(project)
                    seen_names.add(project['name'])

            logger.info(f"完成收集 {len(unique_projects)} 個項目")

            return unique_projects

        except Exception as e:
            logger.error(f"收集項目時出錯: {e}")
            return []

    def _extract_project_info(self, row: WebElement,
                              category_name: str) -> Optional[Project]:
        """
        從表格行中提取項目資訊
        
        Args:
            row: 表格行元素
            category_name: 分類名稱
            
        Returns:
            Optional[Project]: 項目資訊，如果提取失敗則返回 None
        """
        try:
            # 獲取所有列
            cols = row.find_elements(By.TAG_NAME, 'td')

            if len(cols) < 6:  # 確保有足夠的列
                return None

            # 第1列：項目名稱和連結
            project_link = cols[0].find_element(By.TAG_NAME, 'a')
            href = project_link.get_attribute('href')
            title = project_link.text.strip()
            project_name = href.split('/')[-1] if href else None

            if not project_name or not href:
                return None

            # 第2列：文件狀態
            file_state = 'no'  # 默認值
            try:
                file_img = cols[1].find_element(By.TAG_NAME, 'img')
                alt_text = file_img.get_attribute('alt') or ''
                alt_text = alt_text.lower()
                if alt_text == 'yes':
                    file_state = 'yes'
                elif alt_text == 'has external files':
                    file_state = 'external'
            except NoSuchElementException:
                pass

            # 第4列：標籤
            tags = []
            if ARGS.tags:
                try:
                    tag_imgs = cols[3].find_elements(By.TAG_NAME, 'img')
                    for tag_img in tag_imgs:
                        alt_text = tag_img.get_attribute('alt')
                        if alt_text:
                            tags.append(alt_text.lower())
                except NoSuchElementException:
                    pass

            # 構建項目資訊
            project_info: Project = {
                'category': category_name,
                'name': project_name,
                'title': title,
                'url': href,
                'file_state': file_state,
                'tags': tags,
                'info': None
            }

            return project_info

        except Exception as e:
            logger.warning(f"提取項目資訊時出錯: {e}")
            return None

    def get_project_downloads(self, project_url: str) -> List[Dict]:
        """
        獲取項目的下載連結
        
        Args:
            project_url: 項目URL
            
        Returns:
            List[Dict]: 下載連結列表
        """
        downloads = []

        try:
            # 訪問項目頁面
            logger.info(f"正在訪問項目頁面: {project_url}")
            self.driver.get(project_url)

            # 等待頁面加載
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body")))

            # 使用 BeautifulSoup 解析頁面
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # 查找下載連結
            download_links = soup.find_all('a', href=re.compile(r'/download/'))

            for link in download_links:
                if isinstance(link, Tag):
                    href = link.get('href')
                    if href and isinstance(href, str):
                        download_url = urljoin(self.base_url, href)
                        download_text = link.text.strip()

                        downloads.append({
                            'url': download_url,
                            'text': download_text
                        })

            # 同時查找 SVN 連結
            svn_links = soup.find_all('a', href=re.compile(r'svn'))
            for link in svn_links:
                if isinstance(link, Tag):
                    href = link.get('href')
                    if href and isinstance(href, str) and 'browse' in href:
                        svn_url = urljoin(self.base_url, href)
                        downloads.append({
                            'url': svn_url,
                            'text': 'SVN Repository'
                        })

            return downloads

        except Exception as e:
            logger.error(f"獲取項目下載連結時出錯: {e}")
            return []

    def download_file(self,
                      url: str,
                      project_name: str,
                      filename: Optional[str] = None) -> bool:
        """
        下載文件
        
        Args:
            url: 下載URL
            project_name: 項目名稱
            filename: 文件名（可選）
            
        Returns:
            bool: 是否下載成功
        """
        try:
            # 創建項目目錄
            project_dir = self.download_dir / project_name
            project_dir.mkdir(exist_ok=True)

            # 使用 requests 下載文件（效率更高）
            response = self.session.get(url, stream=True)
            response.raise_for_status()

            # 確定文件名
            if not filename:
                if 'content-disposition' in response.headers:
                    filename = response.headers['content-disposition'].split(
                        'filename=')[-1].strip('"')
                else:
                    filename = os.path.basename(
                        urlparse(url).path) or 'download'

            # 移除無效字符
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

            file_path = project_dir / filename

            # 寫入文件
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"下載成功: {file_path}")

            # 如果是 .tar.gz 文件，自動解壓縮
            if self._is_tar_gz_file(file_path):
                if self._extract_tar_gz(file_path, project_dir):
                    logger.info(f"解壓縮成功: {file_path}")

                    # 可選：刪除原始壓縮檔案
                    if not ARGS.keep_compressed:
                        try:
                            os.remove(file_path)
                            logger.info(f"已刪除原始壓縮檔案: {file_path}")
                        except Exception as e:
                            logger.warning(f"刪除壓縮檔案失敗: {e}")
                else:
                    logger.error(f"解壓縮失敗: {file_path}")
                    return False

            return True

        except Exception as e:
            logger.error(f"下載失敗 {url}: {e}")
            self.failed_downloads.append({'url': url, 'error': str(e)})
            return False

    def _is_tar_gz_file(self, file_path: Path) -> bool:
        """
        檢查文件是否為 .tar.gz 格式
        
        Args:
            file_path: 文件路徑
            
        Returns:
            bool: 是否為 .tar.gz 文件
        """
        try:
            # 檢查文件擴展名
            if file_path.suffix.lower() in [
                    '.gz', '.tgz'
            ] or str(file_path).lower().endswith('.tar.gz'):
                return True

            # 嘗試用 tarfile 檢查文件格式
            return tarfile.is_tarfile(file_path)

        except Exception:
            return False

    def _extract_tar_gz(self, file_path: Path, extract_to: Path) -> bool:
        """
        解壓縮 .tar.gz 文件
        
        Args:
            file_path: 壓縮文件路徑
            extract_to: 解壓縮目標目錄
            
        Returns:
            bool: 解壓縮是否成功
        """
        try:
            with tarfile.open(file_path, 'r:gz') as tar:
                # 安全性檢查：確保解壓縮路徑在目標目錄內
                members = tar.getmembers()
                for member in members:
                    if member.name.startswith('/') or '..' in member.name:
                        logger.warning(f"跳過不安全的路徑: {member.name}")
                        continue

                    # 解壓縮到目標目錄
                    tar.extract(member, extract_to)

                logger.info(f"成功解壓縮 {len(members)} 個文件到 {extract_to}")
                return True

        except tarfile.ReadError:
            logger.error(f"無法讀取壓縮文件: {file_path}")
            return False
        except Exception as e:
            logger.error(f"解壓縮時出錯: {e}")
            return False

    def crawl_project(self, project: Project) -> bool:
        """
        爬取單個項目
        
        Args:
            project: 項目資訊
            
        Returns:
            bool: 是否成功
        """
        project_name = project['name']

        if project_name in self.processed_projects:
            logger.info(f"項目 {project_name} 已經處理過")
            return True

        logger.info(f"開始處理項目: {project_name} (分類: {project['category']})")

        try:
            # 檢查是否需要下載項目文件
            if not ARGS.project_info and project['file_state'] != 'yes':
                logger.info(f"項目 {project_name} 跳過 (ARGS.project_info=False)")
                self.processed_projects.add(project_name)
                return True

            if project['file_state'] == 'yes':
                # 使用固定的下載連結格式
                download_url = f"{self.base_url}/download/{project_name}"
                logger.info(f"準備下載項目文件: {download_url}")

                # 下載文件
                if self.download_file(download_url, project_name):
                    logger.info(f"項目 {project_name} 下載成功")
                    self.processed_projects.add(project_name)
                    return True
                else:
                    logger.warning(f"項目 {project_name} 下載失敗")
                    return False

            elif project['file_state'] == 'no':
                logger.info(f"項目 {project_name} 無可下載文件 (file_state: no)")
                self.processed_projects.add(project_name)
                return True

            elif project['file_state'] == 'external':
                logger.info(f"項目 {project_name} 使用外部文件 (file_state: external)")
                self.processed_projects.add(project_name)
                return True

            else:
                logger.info(
                    f"項目 {project_name} 跳過 (file_state: {project['file_state']})"
                )
                self.processed_projects.add(project_name)
                return False

        except Exception as e:
            logger.error(f"處理項目 {project_name} 時出錯: {e}")
            return False

    def crawl_all_projects(self, max_projects: Optional[int] = None) -> None:
        """
        爬取所有項目
        
        Args:
            max_projects: 最大項目數（可選，用於測試）
        """
        logger.info("開始爬取所有項目")

        # 獲取項目列表
        projects = self.get_project_list()

        # 如果不是項目資訊模式，只處理有文件的項目
        if not ARGS.project_info:
            downloadable_projects = [
                p for p in projects if p['file_state'] == 'yes'
            ]
            logger.info(
                f"過濾後可下載項目: {len(downloadable_projects)}/{len(projects)}")
            projects = downloadable_projects

        # 去除已下載過的
        projects = [
            p for p in projects if p['name'] not in self.processed_projects
        ]

        # 限制項目數量（如果指定）
        if max_projects:
            projects = projects[:max_projects]

        # 處理每個項目
        success_count = 0
        for i, project in enumerate(projects, 1):
            logger.info(
                f"處理項目 {i}/{len(projects)}: {project['name']} (分類: {project['category']})"
            )

            if self.crawl_project(project):
                success_count += 1

            # 添加延遲避免被封鎖
            time.sleep(2)

        # 輸出統計
        logger.info(f"爬取完成！成功處理 {success_count}/{len(projects)} 個項目")
        if self.failed_downloads:
            logger.info(f"失敗的下載: {len(self.failed_downloads)} 個")

    def save_failed_downloads(self,
                              filename: str = "failed_downloads.json") -> None:
        """
        儲存失敗的下載列表
        
        Args:
            filename: 文件名
        """
        if self.failed_downloads:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.failed_downloads,
                          f,
                          indent=2,
                          ensure_ascii=False)
            logger.info(f"失敗的下載已儲存到 {filename}")


def main():
    """
    主函數
    """
    if ARGS.clean_download_path:
        shutil.rmtree(ARGS.download_path)

    # 創建爬蟲實例
    crawler = OpenCoresCrawler(headless=ARGS.headless,
                               download_dir=ARGS.download_path)

    try:
        USERNAME = os.getenv("OPENCORES_USERNAME")
        PASSWORD = os.getenv("OPENCORES_PASSWORD")

        print(f'login with username: {USERNAME}')

        if not USERNAME or not PASSWORD:
            raise ValueError(
                "OPENCORES_USERNAME and OPENCORES_PASSWORD must be set")

        # 登入
        if not crawler.login(USERNAME, PASSWORD):
            print("登入失敗，請檢查用戶名和密碼")
            return

        crawler.crawl_all_projects()

        print("爬取完成！")

    finally:
        # 確保清理資源
        if hasattr(crawler, 'driver'):
            crawler.driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='OpenCores Crawler')
    parser.add_argument('--headless',
                        type=bool,
                        default=False,
                        help='是否使用無頭模式')
    parser.add_argument('--tags',
                        action='store_true',
                        default=False,
                        help='是否包含標籤')
    parser.add_argument('--project-info',
                        action='store_true',
                        default=False,
                        help='是否包含項目資訊')
    parser.add_argument('--keep-compressed',
                        action='store_true',
                        default=False,
                        help='是否保留壓縮檔案')
    parser.add_argument('--download-path',
                        type=str,
                        default='downloads',
                        help='下載路徑')
    parser.add_argument('--clean-download-path',
                        action='store_true',
                        default=False,
                        help='是否清空下載路徑')
    ARGS = parser.parse_args()
    main()
