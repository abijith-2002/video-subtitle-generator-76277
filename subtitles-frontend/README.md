# Subtitles Frontend

This is a React frontend for the Video Subtitle Generator application.

## Features

- Upload a video file (MP4, AVI, MOV, etc.)
- Track subtitle generation progress and download `.srt` file
- Interact with a FastAPI backend via REST

## Getting Started

1. Configure the backend API URL in `.env`:
   ```
   REACT_APP_BACKEND_API_URL=http://localhost:8000
   ```
   Change if backend is remote.

2. Install dependencies:
   ```
   npm install
   ```

3. Run the app:
   ```
   npm start
   ```

The frontend runs on [http://localhost:3000](http://localhost:3000) by default.
