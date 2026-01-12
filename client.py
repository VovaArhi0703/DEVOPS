import requests
import base64
import os

# --- НАСТРОЙКИ ---
# Вставь сюда свою ссылку на функцию
FUNCTION_URL = "https://functions.yandexcloud.net/d4e3umuouuffh8s3lnbo"

# Вставь сюда имя своего бакета (например, photos-project)
BUCKET_NAME = "photos-project"


def upload_photo():
    print("\n--- 1. ЗАГРУЗКА ФОТО ---")
    # Убираем кавычки, если пользователь скопировал путь как "C:\..."
    file_path = input("Введи имя: ").strip().strip('"')
    description = input("Придумай описание: ")

    if not os.path.exists(file_path):
        print("❌ Ошибка: Файл не найден!")
        return

    try:
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            filename = os.path.basename(file_path)

            payload = {
                "filename": filename,
                "description": description,
                "file_content": encoded_string
            }

            print("Отправка...")
            response = requests.post(FUNCTION_URL, json=payload)

            if response.status_code == 200:
                print(f"✅ Успешно! ID: {response.json().get('id')}")
            else:
                print(f"❌ Ошибка сервера: {response.text}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")


def list_photos():
    print("\n--- 2. СПИСОК ФОТО ---")
    response = requests.get(FUNCTION_URL)

    if response.status_code != 200:
        print(f"❌ Ошибка получения списка: {response.text}")
        return

    data = response.json()
    photos = data.get('photos', [])

    if not photos:
        print("Список пуст.")
    else:
        for p in photos:
            print(f"[ID: {p['id']}]")
            print(f"   📝 Описание: {p['description']}")
            print(f"   📅 Дата: {p['created_at']}")
            print(f"   🔗 Ссылка: https://storage.yandexcloud.net/{BUCKET_NAME}/{p['object_key']}")
            print("-" * 30)


def delete_photo():
    print("\n--- 3. УДАЛЕНИЕ ФОТО ---")
    photo_id = input("Введите ID фото (скопируйте из списка): ").strip()

    if not photo_id:
        print("ID не может быть пустым.")
        return

    print("Удаление...")
    # Отправляем DELETE запрос с ID в теле (как мы настроили в функции)
    response = requests.delete(FUNCTION_URL, json={"id": photo_id})

    if response.status_code == 200:
        print("✅ Фото успешно удалено из базы данных.")
    else:
        print(f"❌ Ошибка: {response.text}")


def update_photo():
    print("\n--- 4. ОБНОВЛЕНИЕ ОПИСАНИЯ ---")
    photo_id = input("Введите ID фото (скопируйте из списка): ").strip()
    new_desc = input("Введите новое описание: ").strip()

    if not photo_id or not new_desc:
        print("ID и описание обязательны.")
        return

    print("Обновление...")
    # Отправляем PATCH запрос
    response = requests.patch(FUNCTION_URL, json={"id": photo_id, "description": new_desc})

    if response.status_code == 200:
        print("✅ Описание обновлено.")
    else:
        print(f"❌ Ошибка: {response.text}")


# --- ГЛАВНОЕ МЕНЮ ---
while True:
    print("\n=== PHOTO API CLIENT ===")
    print("1 - Загрузить фото")
    print("2 - Показать список")
    print("3 - Удалить фото")
    print("4 - Изменить описание")
    print("0 - Выход")

    mode = input("\nВаш выбор: ")

    if mode == '1':
        upload_photo()
    elif mode == '2':
        list_photos()
    elif mode == '3':
        delete_photo()
    elif mode == '4':
        update_photo()
    elif mode == '0':
        break
    else:
        print("Неверный ввод")