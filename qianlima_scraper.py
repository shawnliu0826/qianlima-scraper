import time
import datetime
import requests
import pandas as pd
import os
import random
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- 配置区域 ---
CONFIG = {
    # 千里马网站账号密码
    "USERNAME": "SHHZ090728",
    "PASSWORD": "WXHZ12345",
    
    # 企业微信webhook
    "WEBHOOK_URL": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=deb7e014-5d8d-4224-8ce9-29ad2dd69d0f",
    
    # 关键词配置
    "KEYWORDS": ["超声波多普勒", "ADCP", "农业水价综合改革", "量水设施", "城市生命线", "水文站提升改造", "水文提档升级", "续建配套与现代化", "雷达水位计", "雷达液位计", "防汛监测", "内涝"],
    
    # 关键词筛选条件配置
    "KEYWORD_FILTERS": {
        "超声波多普勒": ["水文", "水利", "水务"],
        "ADCP": ["水文", "水利", "水务"],
        "农业水价综合改革": ["水位", "流量"],
        "量水设施": ["水位", "流量", "易涝点", "地埋式"],
        "城市生命线": ["水位", "流量", "易涝点", "地埋式"],
        "续建配套与现代化": ["水位", "流量", "易涝点", "地埋式"],
        "内涝": ["水位", "流量", "易涝点", "地埋式"],
        "水文站提升改造": [],  # 不需要额外筛选
        "水文提档升级": [],  # 不需要额外筛选
        "防汛监测": ["水位", "流量", "易涝点"],
        "雷达水位计": [],  # 不需要额外筛选
        "雷达液位计": ["水文", "水利", "水务", "灌区"],  
    },
    
    # 网站配置
    "LOGIN_URL": "https://vip.qianlima.com/login/",
    "SEARCH_URL": "https://search.vip.qianlima.com/index.html",
    
    # 抓取配置
    "REQUEST_INTERVAL": 5,
    "SEARCH_DAYS": 1,  # 搜索昨天的项目信息
    
    # 调试配置
    "DEBUG": False  # 设置为False以避免输出DEBUG级别的日志
}

# 设置日志
logging.basicConfig(
    level=logging.DEBUG if CONFIG["DEBUG"] else logging.INFO,
    format='[%(asctime)s][%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger()

def setup_webdriver():
    """配置并返回WebDriver实例"""
    logger.info("初始化WebDriver...")
    
    # Chrome在本地环境的配置
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    )
    
    try:
        # 使用ChromeDriverManager自动下载匹配的ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info(f"浏览器启动成功: {driver.name}")
        return driver
    except Exception as e:
        logger.error(f"初始化WebDriver失败: {str(e)}")
        raise

def read_keywords():
    """读取关键词列表"""
    logger.info("获取搜索关键词...")
    
    # 优先使用配置中的关键词列表
    if CONFIG["KEYWORDS"]:
        logger.info(f"使用配置中的关键词，共{len(CONFIG['KEYWORDS'])}个")
        return CONFIG["KEYWORDS"], None
    
    # 否则尝试从Excel文件读取
    try:
        if not os.path.exists(CONFIG["KEYWORD_FILE"]):
            error_msg = f"关键词文件不存在: {CONFIG['KEYWORD_FILE']}"
            logger.error(error_msg)
            return None, error_msg
            
        df = pd.read_excel(CONFIG["KEYWORD_FILE"], header=None, names=['keyword'])
        logger.debug(f"读取Excel关键词，原始数据{len(df)}行")
        
        # 数据清洗
        keywords = df['keyword'].astype(str).str.strip()
        cleaned = keywords[keywords.str.len() > 0].dropna().unique().tolist()
        
        if not cleaned:
            error_msg = "文件中没有有效关键词"
            logger.error(error_msg)
            return None, error_msg
            
        logger.info(f"成功读取{len(cleaned)}个关键词")
        return cleaned, None
        
    except Exception as e:
        error_msg = f"读取关键词文件失败：{str(e)}"
        logger.error(error_msg)
        return None, error_msg

def login(driver):
    """登录千里马网站"""
    logger.info(f"开始登录千里马网站: {CONFIG['LOGIN_URL']}")
    
    try:
        # 访问登录页
        driver.get(CONFIG["LOGIN_URL"])
        logger.info(f"页面标题: {driver.title}")
        
        # 输入用户名
        username_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username']"))
        )
        username_input.send_keys(CONFIG["USERNAME"])
        logger.debug("已输入用户名")
        
        # 输入密码
        password_input = driver.find_element(By.CSS_SELECTOR, "input[name='password']")
        password_input.send_keys(CONFIG["PASSWORD"])
        logger.debug("已输入密码")
        
        # 点击登录
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., '登录')]"))
        )
        login_button.click()
        logger.debug("已点击登录按钮")
        
        # 处理安全提示弹窗
        try:
            dialog = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".dialog-account-rsk"))
            )
            logger.debug("检测到安全提示弹窗")
            cancel_btn = dialog.find_element(By.CSS_SELECTOR, ".cancel-btn")
            cancel_btn.click()
            logger.debug("已关闭弹窗")
        except Exception:
            logger.debug("未检测到安全弹窗")
        
        # 验证登录状态
        user_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".user-name.text-over-hidden"))
        )
        username = user_element.text.strip()
        logger.info(f"登录成功，用户名: {username}")
        return True
        
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        return False

def search_and_extract(driver, keyword, start_date_str, end_date_str):
    """执行搜索并提取结果"""
    logger.info(f"开始搜索关键词: {keyword}")
    results = []
    
    try:
        # 导航到搜索页
        driver.get(CONFIG["SEARCH_URL"])
        time.sleep(3)
        
        # 输入搜索关键词
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input.form-control-input"))
        )
        search_input.clear()
        search_input.send_keys(keyword)
        logger.debug(f"已输入关键词: {keyword}")
        
        # 点击搜索
        search_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn.btn-danger"))
        )
        search_button.click()
        logger.debug("搜索请求已发送")
        time.sleep(CONFIG["REQUEST_INTERVAL"])
        
        # 设置时间筛选
        try:
            # 展开时间筛选器
            time_filter = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "TimeFilter"))
            )
            time_filter.click()
            logger.debug("已点击时间筛选器")
            time.sleep(2)
            
            # 选择自定义时间
            custom_date_option = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#TimeFilter .listItem4"))
            )
            driver.execute_script("arguments[0].click();", custom_date_option)
            logger.debug("已选择自定义时间范围")
            time.sleep(2)
            
            # 设置开始时间
            begin_time_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "beginTime"))
            )
            begin_time_input.clear()
            begin_time_input.send_keys(start_date_str)
            logger.debug(f"已设置开始时间: {start_date_str}")
            
            # 设置结束时间
            end_time_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "endTime"))
            )
            end_time_input.clear()
            end_time_input.send_keys(end_date_str)
            logger.debug(f"已设置结束时间: {end_date_str}")
            
            # 点击页面空白处关闭日期选择器
            driver.execute_script("document.querySelector('.container-l').click();")
            time.sleep(2)
            
            # 点击搜索按钮应用筛选
            confirm_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#TimeFilter .confirm-btn"))
            )
            confirm_btn.click()
            logger.debug("时间筛选已应用")
            time.sleep(5)
            
        except Exception as e:
            logger.warning(f"时间筛选异常: {str(e)}")
        
        # 等待结果加载
        time.sleep(8)
        
        # 检查是否有结果
        try:
            no_data = driver.find_element(By.CSS_SELECTOR, ".no-data")
            if no_data.is_displayed():
                logger.info(f"关键词 '{keyword}' 无搜索结果")
                return []
        except:
            pass
        
        # 提取搜索结果
        items = driver.find_elements(By.CSS_SELECTOR, ".con-content")
        logger.info(f"找到 {len(items)} 条搜索结果")
        
        # 解析结果
        for item in items:
            try:
                # 提取标题和链接
                title_elem = item.find_element(By.CSS_SELECTOR, "a.con-title")
                title = title_elem.text.strip()
                link = title_elem.get_attribute('href')
                
                # 提取日期
                date_elem = item.find_element(By.CSS_SELECTOR, "p.con-time")
                date_str = date_elem.text.strip()
                
                # 验证日期范围
                try:
                    item_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    
                    # 如果日期在范围内，再检查内容筛选条件
                    if start_date <= item_date <= end_date:
                        # 检查是否需要内容筛选
                        if keyword in CONFIG.get("KEYWORD_FILTERS", {}) and CONFIG["KEYWORD_FILTERS"][keyword]:
                            # 只有当筛选关键词列表不为空时才进行内容筛选
                            try:
                                # 提取摘要内容（如果有的话）
                                content_elem = item.find_element(By.CSS_SELECTOR, "p.con-abs")
                                content_text = content_elem.text.strip().lower()
                                
                                # 获取该关键词的筛选条件
                                filter_keywords = CONFIG["KEYWORD_FILTERS"][keyword]
                                
                                # 检查是否满足筛选条件（标题或内容中包含任一筛选关键词）
                                meets_filter = False
                                for filter_kw in filter_keywords:
                                    if filter_kw.lower() in title.lower() or filter_kw.lower() in content_text:
                                        meets_filter = True
                                        logger.debug(f"结果满足筛选条件 '{filter_kw}': {title[:30]}...")
                                        break
                                
                                # 如果不满足筛选条件，跳过此结果
                                if not meets_filter:
                                    logger.debug(f"结果不满足筛选条件: {title[:30]}...")
                                    continue
                                
                            except Exception as e:
                                # 如果无法提取内容，保守地包含该结果
                                logger.debug(f"无法提取内容进行筛选，将包含该结果: {str(e)}")
                        
                        # 通过所有筛选，添加到结果
                        results.append({
                            'title': title,
                            'link': link,
                            'date': date_str,
                            'keyword': keyword
                        })
                        logger.debug(f"添加结果: {title[:30]}...")
                except ValueError:
                    logger.warning(f"日期格式错误: {date_str}")
                    
            except Exception as e:
                logger.warning(f"解析结果项异常: {str(e)}")
        
        logger.info(f"关键词 '{keyword}' 找到 {len(results)} 条有效结果")
        return results
        
    except Exception as e:
        logger.error(f"搜索异常: {str(e)}")
        return []

def send_wechat_message(title, content, results=None, keywords=None):
    """发送企业微信消息"""
    logger.info(f"准备发送企业微信消息: {title}")
    headers = {"Content-Type": "application/json"}
    
    try:
        # 构建消息内容
        if results and len(results) > 0:
            yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            
            # 按关键词分组
            keyword_results = {}
            for result in results:
                kw = result['keyword']
                if kw not in keyword_results:
                    keyword_results[kw] = []
                keyword_results[kw].append(result)
            
            # 准备所有消息项目
            all_items = []
            for kw, kw_results in keyword_results.items():
                for result in kw_results:
                    item = f"• [{result['title']}]({result['link']}) ({kw})\n"
                    all_items.append(item)
            
            # Markdown消息字符限制约为4000字节
            # 估计每个消息项平均长度，决定每批发送多少条
            avg_length = sum(len(item) for item in all_items) / len(all_items)
            items_per_batch = min(len(all_items), int(3800 / avg_length))  # 留出一些余量
            
            # 分批次发送
            for i in range(0, len(all_items), items_per_batch):
                batch = all_items[i:i+items_per_batch]
                
                # 合并这批消息
                markdown_content = f"## 昨日 ({yesterday}) 招标信息列表\n\n"
                markdown_content += ''.join(batch)
                
                # 如果不是第一批，添加说明
                if i > 0:
                    markdown_content = f"## 昨日 ({yesterday}) 招标信息列表(续{i//items_per_batch + 1})\n\n" + ''.join(batch)
                
                data = {
                    "msgtype": "markdown",
                    "markdown": {
                        "content": markdown_content
                    }
                }
                response = requests.post(CONFIG["WEBHOOK_URL"], json=data, headers=headers, timeout=10)
                response.raise_for_status()
                
                # 如果还有下一批，等待1分钟再发
                if i + items_per_batch < len(all_items):
                    logger.info(f"等待60秒后发送下一批消息...")
                    time.sleep(60)
            
            logger.info("企业微信消息发送成功")
            return True
            
        else:
            # 没有结果时的消息
            yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            no_result_msg = f"昨日 ({yesterday}) 无招标信息\n\n"
            no_result_msg += "系统已自动搜索，但未找到符合条件的招标信息。"
            
            data = {
                "msgtype": "text",
                "text": {
                    "content": no_result_msg
                }
            }
            
            # 发送请求
            response = requests.post(CONFIG["WEBHOOK_URL"], json=data, headers=headers, timeout=10)
            response.raise_for_status()
            response_json = response.json()
            
            if response_json.get("errcode") == 0:
                logger.info("企业微信消息发送成功")
                return True
            else:
                logger.error(f"企业微信消息发送失败: {response_json}")
                return False
        
    except Exception as e:
        logger.error(f"发送企业微信消息失败: {str(e)}")
        return False

def main():
    """主函数"""
    logger.info("======== 招标信息抓取任务开始 ========")
    
    # 读取关键词列表
    keywords, error = read_keywords()
    if error:
        logger.error(f"初始化失败: {error}")
        send_wechat_message("招标信息抓取失败", f"错误信息: {error}", results=[], keywords=[])
        return {"success": False, "error": error}
    
    # 初始化WebDriver
    driver = None
    try:
        driver = setup_webdriver()
        
        # 登录网站
        if not login(driver):
            error_msg = "登录千里马网站失败"
            logger.error(error_msg)
            send_wechat_message("招标信息抓取失败", f"错误信息: {error_msg}", results=[], keywords=[])
            return {"success": False, "error": error_msg}
            
        # 计算时间范围 - 搜索昨天的数据
        today = datetime.date.today()
        end_date = today - datetime.timedelta(days=1)  # 昨天
        start_date = end_date  # 只搜索昨天一天
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        logger.info(f"搜索时间范围: {start_date_str} 至 {end_date_str}")
        
        # 遍历关键词搜索
        all_results = []
        processed_keywords = set()  # 添加一个集合来追踪已处理的关键词
        unique_titles = set()  # 添加一个集合来追踪已处理的标题，用于去重
        
        for idx, keyword in enumerate(keywords, 1):
            logger.info(f"处理关键词 ({idx}/{len(keywords)}): {keyword}")
            results = search_and_extract(driver, keyword, start_date_str, end_date_str)
            
            # 过滤重复结果
            for result in results:
                if result['title'] not in unique_titles:
                    unique_titles.add(result['title'])
                    all_results.append(result)
                else:
                    logger.debug(f"跳过重复标题: {result['title'][:30]}...")
            
            processed_keywords.add(keyword)  # 将已处理的关键词添加到集合中
            time.sleep(random.uniform(1, 3))
        
        # 验证所有关键词都已处理
        if len(processed_keywords) != len(keywords):
            missed_keywords = set(keywords) - processed_keywords
            logger.warning(f"未处理的关键词: {missed_keywords}")
        
        # 排序结果
        sorted_results = sorted(all_results, key=lambda x: x['date'], reverse=True)
        logger.info(f"搜索完成，共找到 {len(sorted_results)} 条结果")
        
        if sorted_results:
            # 发送企业微信通知
            title = f"昨日招标信息 ({len(sorted_results)}条)"
            content = f"搜索时间范围: {start_date_str} 至 {end_date_str}"
            send_result = send_wechat_message(
                title, 
                content, 
                results=sorted_results, 
                keywords=keywords
            )
            
            if send_result:
                logger.info("任务完成，消息已成功推送到企业微信")
            else:
                logger.warning("任务完成，但企业微信消息推送失败")
            
            return {
                "success": True,
                "count": len(sorted_results)
            }
        else:
            logger.info("未找到符合条件的招标信息")
            send_wechat_message("昨日无招标信息", "未找到符合条件的招标信息", results=[], keywords=keywords)
            return {"success": True, "count": 0}
            
    except Exception as e:
        error_msg = f"任务执行异常: {str(e)}"
        logger.error(error_msg)
        send_wechat_message("招标信息抓取失败", f"错误信息: {error_msg}", results=[], keywords=keywords if 'keywords' in locals() else [])
        return {"success": False, "error": error_msg}
        
    finally:
        # 关闭WebDriver
        if driver:
            try:
                driver.quit()
                logger.info("WebDriver已关闭")
            except Exception as e:
                logger.warning(f"关闭WebDriver异常: {str(e)}")
        
        logger.info("======== 招标信息抓取任务结束 ========")

# 本地测试入口
if __name__ == "__main__":
    main()
