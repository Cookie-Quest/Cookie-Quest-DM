from flask import Flask, render_template, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from colorama import Fore, Style, Back, init
import datetime
import sched
import time

init()

app = Flask(__name__)

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

        # Find the "Manage Cookies" link
def check_manage_cookies_link(driver):
        try:
            # Find the "Manage Cookies" link by searching for its text content
            manage_cookies_link_xpath = "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'manage cookies')]"

            manage_cookies_link = driver.find_element(By.XPATH, manage_cookies_link_xpath)

            # Check if the link is clickable (optional)
            if manage_cookies_link.is_enabled():
                print(f"{Fore.GREEN}{Back.WHITE}Manage Cookies link found and is clickable.{Style.RESET_ALL}")
                # Click the link if needed
                driver.execute_script("arguments[0].click();", manage_cookies_link)
                return True
            else:
                print(f"{Fore.RED}{Back.WHITE}Manage Cookies link found but is not clickable.{Style.RESET_ALL}")

        except NoSuchElementException:
            print(f"{Fore.RED}{Back.WHITE}No 'Manage Cookies' link found.{Style.RESET_ALL}")

        return False

def scan_website(website_url, banner_identifiers):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    service = Service('./driver/chromedriver.exe')
    driver = webdriver.Chrome(service=service, options=chrome_options)

    manage_cookies_link_present = check_manage_cookies_link(driver)  # Move this line here

    print(f"{Fore.GREEN}Scanned website:{Style.RESET_ALL}{Fore.CYAN}{website_url}{Style.RESET_ALL}")
    driver.get(website_url)
    print(f"{Fore.GREEN}Page title:{Style.RESET_ALL}{Fore.CYAN}{driver.title}{Style.RESET_ALL}")

    trustarc_present = check_trustarc(driver)
    osano_present = check_and_report_banner(driver)

    manage_cookies_button = False
    ok_button = False
    button_type = "None"
    # manage_cookies_link_present = False  # Remove this line since it's already initialized above

    if trustarc_present or osano_present:
        consent_banner_div = None

        for identifier_type, identifier_value in banner_identifiers:
            try:
                wait = WebDriverWait(driver, 5)

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

                    if "Manage Cookies" in button.text:
                        button_type = "Type1 (Manage Cookies)"
                        break  # Break out of the loop once "Manage Cookies" is found

                    if "OK" in button.text or "Okay" in button.text:
                        button_type = "Type1 (Okay)"
                        break  # Break out of the loop once "OK" or "Okay" is found

                    # Check if both "Manage Cookies" and "OK"/"Okay" are present
                if "Manage Cookies" in button.text and ("OK" in button.text or "Okay" in button.text):
                    button_type = "Type2 (Both)"
                else:
                    print(f"{Fore.RED}No buttons found in the consent banner{Style.RESET_ALL}")

                break

            except TimeoutException:
                continue

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
    cookie_data = []

    for cookie in cookies:
        if cookie['name'] in cookie_names:
            print(f"{Fore.GREEN}Cookie Name: {Style.RESET_ALL}{Fore.CYAN}{cookie['name']}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Domain: {Style.RESET_ALL}{Fore.CYAN}{cookie['domain']}{Style.RESET_ALL}")
            expiry_timestamp = get_cookie_expiry(cookie)
            expiry_formatted = format_expiry(expiry_timestamp)
            print(f"{Fore.GREEN}Expires: {Style.RESET_ALL}{Fore.CYAN}{expiry_formatted}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Secure: {Style.RESET_ALL}{Fore.CYAN}{cookie['secure']}{Style.RESET_ALL}")

            banner_present = check_and_report_banner(driver)

            ccm_implemented = "Yes" if trustarc_present or osano_present else "No"
            num_buttons = len(buttons) if banner_present else 0
            consent_banner = "Yes" if banner_present else "No"
            provider = "TrustArc" if trustarc_present else "Osano" if osano_present else "None"
            pop_up_working = "Yes" if trustarc_present or osano_present else "No"
            manage_cookies_link = "Yes" if manage_cookies_link_present else "No"

            duration = calculate_cookie_duration(expiry_timestamp)
            if duration is not None:
                duration_str = str(duration)
                print(f"{Fore.GREEN}Time until expiry: {Style.RESET_ALL}{Fore.CYAN}{duration_str}{Style.RESET_ALL}")

                cookie_data.append({
                    "name": cookie['name'],
                    "domain": cookie['domain'],
                    "expiry": expiry_formatted,
                    "secure": cookie['secure'],
                    "ccmImplemented": ccm_implemented,
                    "consentBanner": consent_banner,
                    "provider": provider,
                    "popUpWorking": pop_up_working,
                    "buttonType": button_type,
                    "manageCookiesLink": manage_cookies_link,
                    "Duration": duration if duration is not None else "Session Cookie (no explicit expiry)"
                })

    driver.quit()

    return cookie_data

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan_cookies')
def scan_cookies():
    
    website_urls = [
        'https://ironwoodins.com/',
        'https://www.linqbymarsh.com/linq/auth/login'
        'https://icip.marshpm.com/FedExWeb/',
        'https://www.marshmanagement.com/',
        'https://www.linqbymarsh.com/blueicyber/',
        'https://services.marshspecialty.com/msp-web/register?division=MSP&client=SF',
        'https://www.dovetailexchange.com/Account/Login',
        'https://www.victorinsurance.it/',
        'https://www.sanint.it/',
        'https://www.victorinsurance.nl/',
        'https://www.marshunderwritingsubmissioncenter.com',
        'https://nordicportal.marsh.com/dk/crm/crm_internet.nsf',
        'https://victorinsurance.nl/versekeraars/'
    ]

    banner_identifiers = [
        ("ID", "truste-consent-track"),
        ("CLASS_NAME", "osano-cm-dialog__buttons"),
        ("ID", "osano-cm-buttons")
    ]

    cookie_data = []

    for url in website_urls:
        
        cookies = scan_website(url, banner_identifiers)
        cookie_data.extend(cookies)

    return jsonify({"cookies": cookie_data})

if __name__ == "__main__":
    app.run(debug=True)
