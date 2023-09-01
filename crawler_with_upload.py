from flask import Flask, render_template, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from upload_excel_file import upload_excel_file
from excel_reading import excel_reading
import datetime
import time

app = Flask(__name__)


# csv_file_path = "crawler_csv2"
# data = {'page title': [], 'Cookie Name': [], 'Domain': [], 'Expires': [], 'Secure': []}
# printed_info = []



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
        return duration


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
                print(f"Consent banner present on the page:")
                print(f"Number of buttons: {len(buttons)}")
                for idx, button in enumerate(buttons, start=1):
                    print(f"Button {idx} text: {button.text}")
                return True
            else:
                print(f"No buttons found in the consent banner with {identifier_type} '{identifier_value}'.")

        except TimeoutException:
            continue

    return False


def check_trustarc(driver):
    html = driver.page_source
    return "trustarcBanner" in html


# ... (previous imports and functions)

def scan_website(website_url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    service = Service('./driver/chromedriver.exe')
    driver = webdriver.Chrome(service=service, options=chrome_options)

    print(f"Scanned website: {website_url}")
    driver.get(website_url)
    print("Page title:", driver.title)

    # Check for the presence of the trustarcBanner keyword
    trustarc_present = check_trustarc(driver)
    osano_present = check_and_report_banner(driver)

    if trustarc_present and osano_present:
        print("CCM implemented: Yes (both TrustArc and Osano)")
    elif trustarc_present:
        print("CCM implemented: Yes (TrustArc)")
    elif osano_present:
        print("CCM implemented: Yes (Osano)")
    else:
        print("CCM implemented: No")

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
        'JSESSIONID'
    ]

    cookies = driver.get_cookies()
    cookie_data = []

    for cookie in cookies:
        if cookie['name'] in cookie_names:
            print(f"Cookie Name: {cookie['name']}")
            print(f"Domain: {cookie['domain']}")
            expiry_timestamp = get_cookie_expiry(cookie)
            expiry_formatted = format_expiry(expiry_timestamp)
            print(f"Expires: {expiry_formatted}")
            print(f"Secure: {cookie['secure']}")

            duration = calculate_cookie_duration(expiry_timestamp)
            if duration is not None:
                print(f"Time until expiry: {duration}")

            print("-----")

    # Check for consent banners
    banner_present = check_and_report_banner(driver)
    if not banner_present:
        print("No consent banners found on the page.")

    # Find the "Manage Cookies" link
    try:
        manage_cookies_link = driver.find_element(By.PARTIAL_LINK_TEXT, "Manage Cookies")
        print("Manage Cookies link found in the footer.")

        # Use JavaScript to click the "Manage Cookies" link
        driver.execute_script("arguments[0].click();", manage_cookies_link)
        print("Manage Cookies link clicked successfully.")
        # You can further interact with the pop-up if needed

    except NoSuchElementException:
        print("No 'Manage Cookies' link found in the footer.")
        # Adding cookie data to the list
        cookie_data.append({
            "name": cookie['name'],
            "domain": cookie['domain'],
            "expiry": expiry_formatted,
            "secure": cookie['secure']
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
        'https://www.linqbymarsh.com/linq/auth/login',
        'https://icip.marshpm.com/FedExWeb/login.action',
        'https://www.marsh.com/us/home.html',
        'https://www.marsh.com/us/insights/risk-in-context.html',
        'https://www.dovetailexchange.com/Account/Login',
        'https://www.victorinsurance.com/us/en.html',
        'https://www.victorinsurance.it',
        'https://www.victorinsurance.nl',
        'https://www.marshunderwritingsubmissioncenter.com',
        'https://victorinsurance.nl/verzekeraars'
    ]

    cookie_data = []

    for url in website_urls:
        cookies = scan_website(url)
        cookie_data.extend(cookies)

    return jsonify({"cookies": cookie_data})


if __name__ == "__main__":
    app.run(debug=True)