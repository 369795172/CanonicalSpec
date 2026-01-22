# Canonical Frontend Changelog

## 2026-01-21 - Frontend Redesign

### ✨ New Features

1. **Dark Theme Design**
   - Complete redesign with dark color scheme matching RequirementDocGen
   - Modern UI with smooth animations and transitions
   - Responsive design for mobile and desktop

2. **Voice Input**
   - Real-time audio recording with MediaRecorder API
   - Waveform visualization during recording
   - Audio transcription support (requires backend configuration)
   - Visual feedback for recording and transcribing states

3. **Layout Improvements**
   - Left content pane (discovery-pane) for feature details
   - Right sidebar for feature list and quick actions
   - Fixed bottom input controls with voice button and generate button
   - Better visual hierarchy and spacing

### 🎨 UI/UX Changes

- **Color Scheme**: Dark theme with accent colors (#2c6bed)
- **Typography**: Improved font weights and spacing
- **Animations**: Smooth transitions and hover effects
- **Icons**: Lucide React icons throughout
- **Status Badges**: Color-coded feature status indicators

### 🔧 Technical Changes

- **React Hooks**: useState, useEffect, useRef for state management
- **Audio APIs**: MediaRecorder, AudioContext, AnalyserNode for voice features
- **API Integration**: FastAPI backend endpoints
- **Local Storage**: Feature list persistence

### 📝 Files Modified

- `src/App.css` - Complete rewrite with dark theme
- `src/App.jsx` - Added voice recording, layout restructure
- `canonical/api.py` - New FastAPI server for frontend
- `requirements.txt` - Added FastAPI and uvicorn dependencies

### 🚀 Getting Started

1. **Backend**: Start API server
   ```bash
   cd /Users/marvi/AndroidStudioProjects/canonical
   source venv/bin/activate
   uvicorn canonical.api:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Frontend**: Start dev server
   ```bash
   cd /Users/marvi/AndroidStudioProjects/canonical_frontend
   npm run dev
   ```

3. **Access**: http://localhost:5173

### 📋 TODO

- [ ] Configure OpenAI Whisper API for voice transcription
- [ ] Add error handling for API failures
- [ ] Add loading states for better UX
- [ ] Implement feature editing functionality
