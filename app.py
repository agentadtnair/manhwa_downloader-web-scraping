import time,shutil,mimetypes
from lxml import html
import os
import requests
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from flask import Flask, render_template, request, jsonify
from urllib.parse import urlparse

app = Flask(__name__)

BASE_DIR = "manhwa_project/static/manhwa"
MANHWA_FOLDER = os.path.abspath("C:/scraping projects/manhwa_project/static/manhwa")

def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--blink-settings=scriptEnabled=false")  # Disable scripts (not very effective)
    chrome_options.add_argument("--disable-site-isolation-trials")
    driver = webdriver.Chrome(options=chrome_options)
    driver.maximize_window()
    return driver

def download_images(driver, chapter_link, chapter_name, folder_name):
    try:
        driver.get(chapter_link)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div/div[1]/div/div/div/div/div/div/div[1]/div[2]/div/div/div[2]/div/img'))
        )
        
        chapter_folder = os.path.join(folder_name, chapter_name)
        os.makedirs(chapter_folder, exist_ok=True)
        
        images_list = driver.find_elements(By.XPATH, '/html/body/div[1]/div/div[1]/div/div/div/div/div/div/div[1]/div[2]/div/div/div[2]/div/img')
        
        threads = []
        for index, img in enumerate(images_list):
            img_url = img.get_attribute('src')
            if img_url:
                thread = threading.Thread(target=download_image, args=(img_url, chapter_folder, f"page_{index+1}.jpg"))
                threads.append(thread)
                thread.start()
                time.sleep(0.5) 
        
        for thread in threads:
            thread.join()
        
        print(f"Completed downloading chapter: {chapter_name}")
    except Exception as e:
        print(f"Error downloading images for {chapter_name}: {e}")

def download_image(url, folder, filename):
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code == 200:
            file_path = os.path.join(folder, filename)
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(f"Downloaded: {filename}")
        else:
            print(f"Failed to download {url}, Status Code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed for {url}: {e}")

def sanitize_filename(name):
    """ Remove invalid characters from the filename """
    invalid_chars = r'\/:*?"<>|'
    for char in invalid_chars:
        name = name.replace(char, "")
    return name
def get_file_extension(url):
    """Extract file extension from URL or use MIME type"""
    parsed_url = urlparse(url)
    ext = os.path.splitext(parsed_url.path)[1]  # Extract extension from URL path
    
    # If no extension, try using the MIME type
    if not ext:
        mime_type, _ = mimetypes.guess_type(url)
        ext = mimetypes.guess_extension(mime_type) if mime_type else ".jpg"  # Default to .jpg

    return ext

def download_cover_image(driver, manhwa_name, manga_folder):
    try:
        # Locate the cover image element
        cover_element = driver.find_element(By.XPATH, '/html/body/div[1]/div/div[1]/div/div[1]/div/div/div/div[3]/div[1]/a/img')
        
        # Extract the image URL
        cover_url = cover_element.get_attribute('src')

        if not cover_url:
            print("Cover image URL not found.")
            return

        # Define paths
        file_extension = get_file_extension(cover_url)
        print(f"Detected file extension: {file_extension}")
        downloads_folder = "C:/Users/aadit/Downloads"
        final_image_path = os.path.join(manga_folder, "cover"+file_extension)
        temp_filename = sanitize_filename(manhwa_name) + "_cover" + file_extension
        temp_image_path = os.path.join(downloads_folder, temp_filename)

        # Download the image to the Downloads folder
        response = requests.get(cover_url, stream=True)
        if response.status_code == 200:
            with open(temp_image_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(f"Cover image downloaded to {temp_image_path}")

            # Move the image to the manhwa_folder
            os.makedirs(manga_folder, exist_ok=True)  # Ensure the target folder exists
            shutil.move(temp_image_path, final_image_path)
            print(f"Cover image moved to {final_image_path}")

        else:
            print(f"Failed to download cover image, status code: {response.status_code}")

    except Exception as e:
        print(f"Error downloading cover image: {e}")


def scrape_manhwa(manhwa_name):
    dashed_name = manhwa_name.replace(" ", "-").lower()
    dashed_name = dashed_name.replace(":", "")
    dashed_name = dashed_name.replace(" ' ", "")
    driver = create_driver()
    
    try:
        driver.get(f'https://manhwaclan.com/manga/{dashed_name}')
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div/div[1]/div/div[2]/div/div/div/div[1]/div/div[1]/div/div[4]/div/ul/li'))
        )

        page_sources = driver.page_source
        tree = html.fromstring(page_sources)
        manga_folder = os.path.join(MANHWA_FOLDER, dashed_name)
        os.makedirs(manga_folder, exist_ok=True)

        # Download Cover Image
        download_cover_image(driver, manhwa_name, manga_folder)
        rating = driver.find_element(By.XPATH, '/html/body/div[1]/div/div[1]/div/div[1]/div/div/div/div[3]/div[2]/div/div[1]/div[2]/div[1]/span').text
        details = tree.xpath('/html/body/div[1]/div/div[1]/div/div[1]/div/div/div/div[3]/div[2]/div/div[1]/div[@class="post-content_item"]')

        # ✅ Initialize variables to avoid "not assigned" errors
        types = "Unknown"
        genres = "Unknown"
        alternate = "Unknown"

        g = []
        plot_content=[]
        for detail in details:
            detail_title = detail.xpath('./div/h5')[0].text.lower().strip()
            if detail_title == "alternative":
                alternate = detail.xpath('./div[2]')[0].text.strip() or "Unknown"

            elif detail_title == "genre(s)":
                genres = detail.xpath('./div[2]/div/a')
                if len(genres) > 0:
                    g = [genre.text.strip() for genre in genres]
                
                genres = ", ".join(g) if g else "Unknown"

            elif detail_title == "type":
                types = detail.xpath('./div[2]')[0].text.strip() or "Unknown"

        try:
            plots=tree.xpath("/html/body/div[1]/div/div[1]/div/div[2]/div/div/div/div[1]/div/div[1]/div/div[2]/div[1]/p")
            for ln in plots:
                    plt = ln.text
                    plot_content.append(plt) 
                    


        except Exception as e:
            print(f"Error retrieving plot: {e}")

        details_file_path = os.path.join(manga_folder, "details.txt")    
        with open(details_file_path, 'w', encoding='utf-8') as f:
            f.write(f"Rating: {rating}\n")
            f.write(f"Genres: {genres}\n")
            f.write(f"Type: {types}\n")
            f.write(f"Alternative: {alternate}\n")
            f.write(f"Plot: {'*-*'.join(plot_content)}\n")
        print("Details saved to file")

        # Locate chapters
        chapters_list = driver.find_elements(By.XPATH, '/html/body/div[1]/div/div[1]/div/div[2]/div/div/div/div[1]/div/div[1]/div/div[4]/div/ul/li')
        
        for i, chapter in enumerate(reversed(chapters_list), 1):
            chapter_name = f"chapter-{i}"
            chapter_link = f"https://manhwaclan.com/manga/{dashed_name}/{chapter_name}/"
            print(f"Downloading chapter: {chapter_name}")
            download_images(driver, chapter_link, chapter_name, manga_folder)
        
    except Exception as e:
        print(f"Error retrieving chapters: {e}")
    finally:
        driver.quit()
    
    print("Download complete!")


@app.route('/')
def home():
    manhwas = os.listdir(BASE_DIR) if os.path.exists(BASE_DIR) else []
    return render_template('index.html', manhwas=manhwas)

@app.route('/scrape', methods=['GET', 'POST'])
def scrape():
    if request.method == 'POST':
        manhwa_name = request.form.get('manhwa_name')
        if not manhwa_name:
            return jsonify({"success": False, "error": "Manhwa name is required!"})
        try:
            scrape_manhwa(manhwa_name)
            return jsonify({"success": True, "message": f"Scraping {manhwa_name} completed!"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    return render_template('scrape.html')

@app.route('/view_manhwas')
def view_manhwas():
    """Lists all available Manhwas"""
    if not os.path.exists(MANHWA_FOLDER):
        return "Manhwa folder not found!", 404

    manhwas_list = [f for f in os.listdir(MANHWA_FOLDER) if os.path.isdir(os.path.join(MANHWA_FOLDER, f))]
    return render_template('view_manhwas.html', manhwas=manhwas_list)


@app.route('/browse')
def browse():
    return "Manga browsing page coming soon!"  # Replace this with the actual browsing page



@app.route('/view/<manhwa_name>')
def view(manhwa_name):
    chapters_folder = os.path.join(BASE_DIR, manhwa_name)
    details_file = os.path.join(chapters_folder, "details.txt")
    details = {}

    # Read details.txt if it exists
    if os.path.exists(details_file):
        with open(details_file, "r", encoding="utf-8") as file:
            for line in file:
                if ": " in line:
                    key, value = line.strip().split(": ", 1)
                    if value.strip() and value.lower() not in ["unknown", "n/a", "none", "-"]:
                        details[key] = value  # Store only if value is not empty or unknown

    chapters = []
    if os.path.exists(chapters_folder):
        # Get the list of chapters
        chapters = [chapter for chapter in os.listdir(chapters_folder) 
                    if os.path.isdir(os.path.join(chapters_folder, chapter))]

        # Selection Sort using a for loop
        n = len(chapters)
        for i in range(n):
            min_idx = i
            for j in range(i + 1, n):
                # Convert chapter names to integers if possible for numeric sorting
                chapter1 = int(chapters[min_idx]) if chapters[min_idx].isdigit() else chapters[min_idx]
                chapter2 = int(chapters[j]) if chapters[j].isdigit() else chapters[j]

                if chapter1 > chapter2:
                    min_idx = j  # Find the minimum element

            # Swap the found minimum element with the first element
            chapters[i], chapters[min_idx] = chapters[min_idx], chapters[i]

    if not chapters:
        return "No chapters found", 404  # Handle case where no chapters exist

    # Modify chapters to be in "Chapter-{i}" format
    formatted_chapters = [f"chapter-{i+1}" for i in range(len(chapters))]

    # Get first chapter and navigation details
    first_chapter = formatted_chapters[0]  
    current_chapter_index = 0  

    # Determine previous and next chapters
    prev_chapter = formatted_chapters[current_chapter_index - 1] if current_chapter_index > 0 else None
    next_chapter = formatted_chapters[current_chapter_index + 1] if current_chapter_index < len(formatted_chapters) - 1 else None

    return render_template('view.html', 
                           manhwa_name=manhwa_name, 
                           details=details,  
                           first_chapter=first_chapter,
                           chapters=formatted_chapters,
                           prev_chapter=prev_chapter,
                           next_chapter=next_chapter)




    


        


@app.route('/view_images/<manhwa_name>/<chapter_name>')
def view_images(manhwa_name, chapter_name):
    """Displays images for a specific chapter and manages next/previous navigation."""
    chapters_folder = os.path.join(app.static_folder, 'manhwa', manhwa_name)
    
    if not os.path.exists(chapters_folder):
        return "Chapters not found!", 404

    # List all chapters and sort them numerically & alphabetically
    chapters = [chapter for chapter in os.listdir(chapters_folder) 
                if os.path.isdir(os.path.join(chapters_folder, chapter))]

    n = len(chapters)
    for i in range(n):
        min_idx = i
        for j in range(i + 1, n):
            # Convert chapter names to integers if possible for numeric sorting
            chapter1 = int(chapters[min_idx]) if chapters[min_idx].isdigit() else chapters[min_idx]
            chapter2 = int(chapters[j]) if chapters[j].isdigit() else chapters[j]

            if chapter1 > chapter2:
                min_idx = j  # Find the minimum element

        # Swap the found minimum element with the first element
        chapters[i], chapters[min_idx] = chapters[min_idx], chapters[i]

    if not chapters:
        return "No chapters found", 404  # Handle case where no chapters exist

    # Modify chapters to be in "chapter-{i}" format
    formatted_chapters = [f"chapter-{i+1}" for i in range(len(chapters))]

    # Find the correct index of the current chapter
    if chapter_name in formatted_chapters:
        current_chapter_index = formatted_chapters.index(chapter_name)
    else:
        return "Chapter not found", 404  # Handle invalid chapter names

    # Determine previous and next chapters
    prev_chapter = formatted_chapters[current_chapter_index - 1] if current_chapter_index > 0 else None
    next_chapter = formatted_chapters[current_chapter_index + 1] if current_chapter_index < len(formatted_chapters) - 1 else None

    # Get all images in the chapter folder
    chapter_folder = os.path.join(chapters_folder, chapter_name)
    images = sorted(os.listdir(chapter_folder))

    return render_template(
        'view_images.html',
        manhwa_name=manhwa_name,
        chapter_name=chapter_name,
        images=images,
        prev_chapter=prev_chapter,
        next_chapter=next_chapter,
        chapters=formatted_chapters
    )






def get_images(manhwa_name, chapter_name):
    chapter_folder = os.path.join(BASE_DIR, manhwa_name, chapter_name)
    if not os.path.exists(chapter_folder):
        return []
    return sorted([img for img in os.listdir(chapter_folder) if img.endswith('.jpg')])

if __name__ == "__main__":
    app.run(debug=True)