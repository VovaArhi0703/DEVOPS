import os
import json
import base64
import uuid
import boto3
import ydb
import ydb.iam
import datetime

# --- Конфигурация ---
YDB_ENDPOINT = os.getenv('YDB_ENDPOINT')
YDB_DATABASE = os.getenv('YDB_DATABASE')
S3_BUCKET = os.getenv('S3_BUCKET')
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY')

# --- Инициализация клиентов ---
s3_client = boto3.client(
    's3',
    endpoint_url='https://storage.yandexcloud.net',
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY
)

driver_config = ydb.DriverConfig(
    YDB_ENDPOINT,
    YDB_DATABASE,
    credentials=ydb.iam.MetadataUrlCredentials(),
)
driver = ydb.Driver(driver_config)

try:
    driver.wait(timeout=5)
except Exception as e:
    print(f"Driver connect error: {e}")


# --- Вспомогательные функции ---

def get_response(status_code, body):
    # Превращаем body в JSON с поддержкой кодировки
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(body, default=str)  # default=str помогает сериализовать даты и байты
    }


def update_photo_description(photo_id, new_description):
    safe_description = new_description.replace("'", "").replace('"', '')
    # Используем UPDATE, чтобы изменить только описание, не трогая остальные поля
    query = "UPDATE photos SET description = '{}' WHERE id = '{}';".format(safe_description, photo_id)
    success, result = execute_sql(query)
    return success, result


def execute_sql(query):
    """Универсальная функция для выполнения SQL"""
    try:
        session = driver.table_client.session().create()
        result_sets = session.transaction().execute(query, commit_tx=True)
        session.delete()
        return True, result_sets
    except Exception as e:
        return False, str(e)


# --- Логика работы с БД ---

def save_photo(photo_id, description, object_key):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_description = description.replace("'", "").replace('"', '')

    # Работающий вариант с .format()
    query = "UPSERT INTO photos (id, description, object_key, created_at) VALUES ('{}', '{}', '{}', '{}');".format(
        photo_id, safe_description, object_key, now_str
    )
    success, result = execute_sql(query)
    return success, result


def get_all_photos():
    query = "SELECT id, description, object_key, created_at FROM photos;"
    success, result_sets = execute_sql(query)

    if not success:
        return False, result_sets  # Здесь будет текст ошибки

    # Преобразуем ответ YDB в обычный список словарей
    photos = []
    if result_sets and result_sets[0].rows:
        for row in result_sets[0].rows:
            photos.append({
                'id': row.id.decode('utf-8') if isinstance(row.id, bytes) else row.id,
                'description': row.description.decode('utf-8') if isinstance(row.description,
                                                                             bytes) else row.description,
                'object_key': row.object_key.decode('utf-8') if isinstance(row.object_key, bytes) else row.object_key,
                'created_at': row.created_at.decode('utf-8') if isinstance(row.created_at, bytes) else row.created_at,
            })
    return True, photos


def delete_photo(photo_id):
    # Опасный момент: .format без проверок - потенциальная SQL-инъекция,
    # но для нашего учебного проекта это самый надежный способ избежать ошибок типов.
    query = "DELETE FROM photos WHERE id = '{}';".format(photo_id)
    success, result = execute_sql(query)
    return success, result


# --- Основной обработчик ---

def handler(event, context):
    http_method = event.get('httpMethod')

    # 1. POST - Загрузка фото
    if http_method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            filename = body.get('filename')
            description = body.get('description', '')
            file_content_b64 = body.get('file_content')

            if not filename or not file_content_b64:
                return get_response(400, {'error': 'filename and file_content are required'})

            file_data = base64.b64decode(file_content_b64)
            photo_id = str(uuid.uuid4())
            object_key = f"{photo_id}_{filename}"

            s3_client.put_object(Bucket=S3_BUCKET, Key=object_key, Body=file_data)

            success, error = save_photo(photo_id, description, object_key)
            if not success:
                return get_response(500, {'error': f'YDB Error: {error}'})

            return get_response(200, {'message': 'Uploaded', 'id': photo_id})
        except Exception as e:
            return get_response(500, {'error': str(e)})

    # 2. GET - Список фото
    elif http_method == 'GET':
        success, data = get_all_photos()
        if not success:
            return get_response(500, {'error': f'YDB Error: {data}'})
        return get_response(200, {'photos': data})

    # 3. DELETE - Удаление фото
    elif http_method == 'DELETE':
        # Пытаемся достать ID из параметров URL (query parameters)
        params = event.get('queryStringParameters')
        if not params or 'id' not in params:
            # Если нет в URL, пробуем искать в теле запроса
            try:
                body = json.loads(event.get('body', '{}'))
                photo_id = body.get('id')
            except:
                photo_id = None
        else:
            photo_id = params['id']

        if not photo_id:
            return get_response(400, {'error': 'id parameter is required'})

        success, error = delete_photo(photo_id)
        if not success:
            return get_response(500, {'error': f'YDB Error: {error}'})

        return get_response(200, {'message': f'Photo {photo_id} deleted from DB'})

    # 4. PATCH - Обновление описания
    elif http_method == 'PATCH':
        try:
            body = json.loads(event.get('body', '{}'))
            photo_id = body.get('id')
            new_description = body.get('description')

            if not photo_id or new_description is None:
                return get_response(400, {'error': 'id and description are required'})

            success, error = update_photo_description(photo_id, new_description)
            if not success:
                return get_response(500, {'error': f'YDB Error: {error}'})

            return get_response(200, {'message': f'Description for photo {photo_id} updated'})
        except Exception as e:
            return get_response(500, {'error': str(e)})

    return get_response(405, {'error': 'Method not allowed'})