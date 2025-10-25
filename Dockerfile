FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Копируем проект
COPY . .


RUN mkdir -p /app/staticfiles && python manage.py collectstatic --noinput

CMD ["gunicorn", "art_crm.wsgi:application", "--bind", "0.0.0.0:8000"]
