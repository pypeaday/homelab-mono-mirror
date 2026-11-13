FROM python:3.13-alpine
RUN apk add --no-cache ffmpeg
COPY gallery.py /app/gallery.py
VOLUME /reels
EXPOSE 8788
CMD ["python", "/app/gallery.py", "/reels", "--port", "8788", "--host", "0.0.0.0"]
