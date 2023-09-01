from flask import Flask, render_template, jsonify, request, redirect
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from excel_reading import excel_reading
from upload_excel_file import upload_excel_file
from colorama import Fore, Style, Back, init
import pandas as pd
import datetime, sched
import time

app = Flask(__name__)


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.xlsx'):
            file.save("uploaded_file.xlsx")
            return redirect('/scan_cookies')
    return '''
    <!doctype html>
    <title>Upload an Excel File</title>
    <h1>Upload an Excel file</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() == 'xlsx'

def format_expiry(expiry_timestamp):
    if expiry_timestamp is not None:
        expiry_datetime = datetime.datetime.fromtimestamp(expiry_timestamp)
        return expiry_datetime.strftime('%Y-%m-%d %H:%M:%S')
    return "Session Cookie (no explicit expiry)"

def get_cookie_expiry(cookie):
    if 'expiry' in cookie:
        return cookie['expiry']
    elif 'expires' in cookie:
        return cookie['expires']
    elif 'max_age' in cookie:
        return time.time() + cookie['max_age']
    elif 'Expires / Max-Age' in cookie:
        expires_max_age = cookie['Expires / Max-Age']
        parts = expires_max_age.split('/')
        if len(parts) == 2:
            expires_date_str, max_age_str = parts
            expires_date = datetime.datetime.strptime(expires_date_str.strip(), '%a, %d-%b-%Y %H:%M:%S %Z')
            max_age = int(max_age_str.strip())
            return expires_date.timestamp() + max_age
    return None

def calculate_cookie_duration(expiry_timestamp):
    if expiry_timestamp is not None:
        expiry_datetime = datetime.datetime.fromtimestamp(expiry_timestamp)
        current_datetime = datetime.datetime.now()
        duration = expiry_datetime - current_datetime

        hours, remainder = divmod(duration.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        duration_formatted = f"{hours}h {minutes}m {seconds}s"
        return duration_formatted

    return "Session Cookie (no explicit expiry)"

def check_and_report_banner(driver):
    banner_identifiers = [
        ("ID", "truste-consent-track"),
        ("CLASS_NAME", "osano-cm-dialog__buttons"),
        ("ID", "osano-cm-buttons")  # ID for the second banner
    ]
    
    for identifier_type, identifier_value in banner_identifiers:
        try:
            wait = WebDriverWait(driver, 5)  # Reduced waiting time for efficiency
            
            if identifier_type == "ID":
                wait.until(EC.presence_of_element_located((By.ID, identifier_value)))
            elif identifier_type == "CLASS_NAME":
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, identifier_value)))
            
            consent_banner_div = driver.find_element(getattr(By, identifier_type), identifier_value)
            buttons = consent_banner_div.find_elements(By.TAG_NAME, "button")
            if buttons:
                print(f"{Fore.GREEN}Consent banner present on the page:{Style.RESET_ALL}")
                print(f"{Fore.GREEN}Number of buttons: {Style.RESET_ALL}{Fore.CYAN}{len(buttons)}{Style.RESET_ALL}")
                for idx, button in enumerate(buttons, start=1):
                    print(f"{Fore.GREEN}Button {idx} text: {Style.RESET_ALL}{Fore.CYAN}{button.text}{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}No buttons found in the consent banner with {identifier_type} '{identifier_value}'.{Style.RESET_ALL}")
            
        except TimeoutException:
            continue

    return False

def check_trustarc(driver):
    html = driver.page_source
    return "truste" in html

# ... (previous imports and functions)

def scan_website(website_url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    service = Service('./driver/chromedriver.exe')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    

    print(f"{Fore.GREEN}Scanned website:{Style.RESET_ALL}{Fore.CYAN}{website_url}{Style.RESET_ALL}")
    driver.get(website_url)
    print(f"{Fore.GREEN}Page title:{Style.RESET_ALL}{Fore.CYAN}{driver.title}{Style.RESET_ALL}")

    # Check for the presence of the trustarcBanner keyword
    trustarc_present = check_trustarc(driver)
    osano_present = check_and_report_banner(driver)
    buttons = []  # Initialize the buttons list here
    manage_cookies_link_present = False  # Initialize the manage_cookies_link_present variable here


    if trustarc_present and osano_present:
        print(f"{Fore.GREEN}CCM implemented:{Fore.CYAN} Yes (both TrustArc and Osano){Style.RESET_ALL}")
    elif trustarc_present:
        print(f"{Fore.GREEN}CCM implemented:{Fore.CYAN} Yes (TrustArc){Style.RESET_ALL}")
    elif osano_present:
        print(f"{Fore.GREEN}CCM implemented:{Fore.CYAN} Yes (Osano) {Style.RESET_ALL}")
    else:
        print(f"{Fore.GREEN}CCM implemented:{Fore.CYAN} No{Style.RESET_ALL}")

    cookie_names = [
        'osano_consentmanager',
        'osano_consentmanager_uuid',
        'visitor_id395202-hash',
        's_cc',
        'notice_behavior',
        'mbox',
        'ln_or',
        'linq_auth_redirect_addr',
        'at_check',
        '_gid',
        '_gcl_au',
        '_ga',
        'AWSALBCORS',
        'AWSALB',
        'AMCV_7205F0F5559E57A87F000101%40AdobeOrg',
        'JSESSIONID',
        'oktaStateToken',
        'DT'
    ]

    cookies = driver.get_cookies()
    cookie_data = []       #This will be extracted into a PD DF to export as excel spreadsheet

    for cookie in cookies:
        if cookie['name'] in cookie_names:
            print(f"{Fore.GREEN}Cookie Name: {Style.RESET_ALL}{Fore.CYAN}{cookie['name']}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Domain: {Style.RESET_ALL}{Fore.CYAN}{cookie['domain']}{Style.RESET_ALL}")
            expiry_timestamp = get_cookie_expiry(cookie)
            expiry_formatted = format_expiry(expiry_timestamp)
            print(f"{Fore.GREEN}Expires: {Style.RESET_ALL}{Fore.CYAN}{expiry_formatted}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Secure: {Style.RESET_ALL}{Fore.CYAN}{cookie['secure']}{Style.RESET_ALL}")
                        # Check for consent banners
            banner_present = check_and_report_banner(driver)

            # Additional information related to CCM implementation
            ccm_implemented = "Yes" if trustarc_present or osano_present else "No"
            num_buttons = len(buttons) if banner_present else 0
            consent_banner = "Yes" if banner_present else "No"
            provider = "TrustArc" if trustarc_present else "Osano" if osano_present else "None"
            pop_up_working = "Yes" if trustarc_present or osano_present else "No"
            manage_cookies_link = "Yes" if manage_cookies_link_present else "No"


            print("-----")
            
    # Check for consent banners
    banner_present = check_and_report_banner(driver)
    if not banner_present:
        print(f"{Fore.RED}{Back.WHITE}No consent banners found on the page.{Style.RESET_ALL}")

    # Find the "Manage Cookies" link
    try:
        manage_cookies_link = driver.find_element(By.PARTIAL_LINK_TEXT, "Manage Cookies")
        print(f"{Fore.GREEN}{Back.WHITE}Manage Cookies link found in the footer.{Style.RESET_ALL}")
        
        # Use JavaScript to click the "Manage Cookies" link
        driver.execute_script("arguments[0].click();", manage_cookies_link)
        print(f"{Fore.GREEN}{Back.WHITE}Manage Cookies link clicked successfully.{Style.RESET_ALL}")
        # You can further interact with the pop-up if needed
        
    except NoSuchElementException:
        print(f"{Fore.RED}{Back.WHITE}No 'Manage Cookies' link found in the footer.{Style.RESET_ALL}")
        
        duration = calculate_cookie_duration(expiry_timestamp)
        if duration is not None:
            duration_str = str(duration)  # Convert timedelta to string
            print(f"{Fore.GREEN}Time until expiry: {Style.RESET_ALL}{Fore.CYAN}{duration_str}{Style.RESET_ALL}")

            # Adding cookie data to the list
        cookie_data.append({
                "name": cookie['name'],
                "domain": cookie['domain'],
                "expiry": expiry_formatted,
                "secure": cookie['secure'],
                "ccmImplemented": ccm_implemented,
                "numButtons": num_buttons,
                "consentBanner": consent_banner,
                "provider": provider,
                "popUpWorking": pop_up_working,
                "manageCookiesLink": manage_cookies_link,
                "Duration": duration if duration is not None else "Session Cookie (no explicit expiry)"
                
            })

    driver.quit()

    return cookie_data
@app.route('/scan_cookies')
def scan_cookies():
    excel_file = "uploaded_file.xlsx"
    excel_sheet = "Sheet1"
    column = "Website"
    
 
    try:
        df = pd.read_excel(excel_file, sheet_name=excel_sheet)
        if column in df.columns:
            website_urls = df[column].tolist()
        else:
            return jsonify({"error": f"Column '{column}' not found in the Excel file."})
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"})
    
    cookie_data = []  

    for url in website_urls:
        cookies = scan_website(url)  
        cookie_data.extend(cookies)  

    
    df_output = pd.DataFrame(cookie_data)
    df_output.to_excel("output_cookies.xlsx", index=False)  # ***save the data to an Excel file
    
    return jsonify({"cookies": cookie_data})  

def scan_website(website_url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    service = Service('./driver/chromedriver.exe')
    driver = webdriver.Chrome(service=service, options=chrome_options)


    print(f"{Fore.GREEN}Scanned website:{Style.RESET_ALL}{Fore.CYAN}{website_url}{Style.RESET_ALL}")
    driver.get(website_url)
    print(f"{Fore.GREEN}Page title:{Style.RESET_ALL}{Fore.CYAN}{driver.title}{Style.RESET_ALL}")

    # Check for the presence of the trustarcBanner keyword
    trustarc_present = check_trustarc(driver)
    osano_present = check_and_report_banner(driver)
    buttons = []  # Initialize the buttons list here
    manage_cookies_link_present = False  # Initialize the manage_cookies_link_present variable here


    if trustarc_present and osano_present:
        print(f"{Fore.GREEN}CCM implemented:{Fore.CYAN} Yes (both TrustArc and Osano){Style.RESET_ALL}")
    elif trustarc_present:
        print(f"{Fore.GREEN}CCM implemented:{Fore.CYAN} Yes (TrustArc){Style.RESET_ALL}")
    elif osano_present:
        print(f"{Fore.GREEN}CCM implemented:{Fore.CYAN} Yes (Osano) {Style.RESET_ALL}")
    else:
        print(f"{Fore.GREEN}CCM implemented:{Fore.CYAN} No{Style.RESET_ALL}")

    cookie_names = [
        'osano_consentmanager',
        'osano_consentmanager_uuid',
        'visitor_id395202-hash',
        's_cc',
        'notice_behavior',
        'mbox',
        'ln_or',
        'linq_auth_redirect_addr',
        'at_check',
        '_gid',
        '_gcl_au',
        '_ga',
        'AWSALBCORS',
        'AWSALB',
        'AMCV_7205F0F5559E57A87F000101%40AdobeOrg',
        'JSESSIONID',
        'oktaStateToken',
        'DT'
    ]

    cookies = driver.get_cookies()

    cookie_data = []  #This will be extracted into a PD DF to export as excel spreadsheet

    for cookie in cookies:
        if cookie['name'] in cookie_names:
            print(f"{Fore.GREEN}Cookie Name: {Style.RESET_ALL}{Fore.CYAN}{cookie['name']}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Domain: {Style.RESET_ALL}{Fore.CYAN}{cookie['domain']}{Style.RESET_ALL}")
            expiry_timestamp = get_cookie_expiry(cookie)
            expiry_formatted = format_expiry(expiry_timestamp)
            print(f"{Fore.GREEN}Expires: {Style.RESET_ALL}{Fore.CYAN}{expiry_formatted}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Secure: {Style.RESET_ALL}{Fore.CYAN}{cookie['secure']}{Style.RESET_ALL}")
                        # Check for consent banners
            banner_present = check_and_report_banner(driver)

            # Additional information related to CCM implementation
            ccm_implemented = "Yes" if trustarc_present or osano_present else "No"
            num_buttons = len(buttons) if banner_present else 0
            consent_banner = "Yes" if banner_present else "No"
            provider = "TrustArc" if trustarc_present else "Osano" if osano_present else "None"
            pop_up_working = "Yes" if trustarc_present or osano_present else "No"
            manage_cookies_link = "Yes" if manage_cookies_link_present else "No"


            print("-----")

    # Check for consent banners
    banner_present = check_and_report_banner(driver)
    if not banner_present:
        print(f"{Fore.RED}{Back.WHITE}No consent banners found on the page.{Style.RESET_ALL}")

    # Find the "Manage Cookies" link
    try:
        manage_cookies_link = driver.find_element(By.PARTIAL_LINK_TEXT, "Manage Cookies")
        print(f"{Fore.GREEN}{Back.WHITE}Manage Cookies link found in the footer.{Style.RESET_ALL}")

        # Use JavaScript to click the "Manage Cookies" link
        driver.execute_script("arguments[0].click();", manage_cookies_link)
        print(f"{Fore.GREEN}{Back.WHITE}Manage Cookies link clicked successfully.{Style.RESET_ALL}")
        # You can further interact with the pop-up if needed

    except NoSuchElementException:
        print(f"{Fore.RED}{Back.WHITE}No 'Manage Cookies' link found in the footer.{Style.RESET_ALL}")

        duration = calculate_cookie_duration(expiry_timestamp)
        if duration is not None:
            duration_str = str(duration)  # Convert timedelta to string
            print(f"{Fore.GREEN}Time until expiry: {Style.RESET_ALL}{Fore.CYAN}{duration_str}{Style.RESET_ALL}")

            # Adding cookie data to the list
        cookie_data.append({
                "name": cookie['name'],
                "domain": cookie['domain'],
                "expiry": expiry_formatted,
                "secure": cookie['secure'],
                "ccmImplemented": ccm_implemented,
                "numButtons": num_buttons,
                "consentBanner": consent_banner,
                "provider": provider,
                "popUpWorking": pop_up_working,
                "manageCookiesLink": manage_cookies_link,
                "Duration": duration if duration is not None else "Session Cookie (no explicit expiry)"

            })

    driver.quit()

    return cookie_data  # Return the cookie data

@app.route('/')
def index():
    return render_template('index.html')

# @app.route('/scan_cookies')
# def scan_cookies():
#     excel_file = "uploaded_file.xlsx"
#     excel_sheet = "Sheet1"
#     column = "Website"
#
#     # Read the websites from the Excel file
#     try:
#         df = pd.read_excel(excel_file, sheet_name=excel_sheet)
#         if column in df.columns:
#             website_urls = df[column].tolist()
#         else:
#             return jsonify({"error": f"Column '{column}' not found in the Excel file."})
#     except Exception as e:
#         return jsonify({"error": f"An error occurred: {str(e)}"})
#
#     cookie_data = []
#
#     for url in website_urls:
#         cookies = scan_website(url)
#         cookie_data.extend(cookies)
#
#     return jsonify({"cookies": cookie_data})

if __name__ == "__main__":
    app.run(debug=True)
    
    
    
    
    
    
    
    
# s = sched.scheduler(time.time, time.sleep)
# def run_script(sc):
#     # print("Running scheduled scan...")
#     s.enter(150, 1, run_script, (sc,))
# if __name__ == "__main__":
#     s.enter(0, 1, run_script, (s,))
#     s.run()
