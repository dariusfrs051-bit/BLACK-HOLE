# 🕳️ BLACK HOLE — Image Spaghettifier

> Feed it an image. Watch it get destroyed by physics.

BLACK HOLE is a web app that animates any uploaded image being consumed by a black hole — complete with physically-inspired effects including gravitational lensing, spaghettification, gravitational redshift, chromatic aberration, and a final fade past the event horizon.

Built with a **FastAPI** backend and a **Three.js + vanilla JS** frontend, it streams each animation frame in real time via Server-Sent Events (SSE).

---

## ✨ Effects

| Effect | Description |
|---|---|
| **Gravitational Lensing** | Pixels warp toward the center using radial distortion. Strength grows non-linearly as the image approaches the singularity. |
| **Spaghettification** | Tidal forces stretch the image vertically (∝ M/r³) and squeeze it horizontally. Starts subtle, goes catastrophic. |
| **Chromatic Aberration** | Near the photon sphere, extreme lensing splits color channels — red shifts right, blue shifts left. |
| **Gravitational Redshift** | Light loses energy escaping the gravity well. Green and blue channels fade out, leaving a deep red glow. |
| **Event Horizon Fade** | Past 90% of the animation, the image crushes to black. It's gone. |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+

### Installation

```bash
# Clone the repository
git clone https://github.com/dariusfrs051-bit/BLACK-HOLE.git
cd BLACK-HOLE

# Install dependencies
pip install -r requirements.txt
```

### Running the App

```bash
python -m uvicorn api:app --reload
```

Then open your browser at [http://localhost:8000](http://localhost:8000).

---

## 📡 API Reference

### `PUT /feed`
Upload an image to be consumed by the black hole.

- **Body:** `multipart/form-data` with an `image/*` file field named `file`
- **Response:** JSON confirmation

```json
{
  "status": "consumed",
  "filename": "photo.jpg",
  "message": "Connect to GET /stream to watch it fall in."
}
```

---

### `GET /stream`
Stream the animation as Server-Sent Events. Each event payload is a base64-encoded PNG frame.

| Query Param | Default | Description |
|---|---|---|
| `steps` | `80` | Number of animation frames |
| `delay_ms` | `50` | Milliseconds between frames |

The stream ends with a final `SINGULARITY` event.

---

### `GET /`
Serves the full web UI (`index.html`).

---

## 🛠️ Tech Stack

- **Backend:** FastAPI, Uvicorn, Pillow, NumPy
- **Frontend:** Vanilla JS, Three.js (animated cosmic background), Orbitron + Space Mono fonts
- **Streaming:** Server-Sent Events (SSE)

---

## 📦 Dependencies

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
pillow>=10.0.0
numpy>=1.24.0
python-multipart>=0.0.9
```

---

## 📄 License

This project is open source. See [LICENSE](LICENSE) for details.
