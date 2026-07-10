"""
Dental AI Diagnosis System — Standalone Server
=============================================
Requirements: pip install flask

Run: python dental_ai_standalone.py
Open: http://localhost:5000
"""

import sqlite3
import json
import base64
import time
import os
from flask import Flask, request, jsonify, g

app = Flask(__name__)
DB_PATH = "dental_ai.db"

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                image_base64 TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                overall_confidence REAL NOT NULL DEFAULT 0,
                conditions_found INTEGER NOT NULL DEFAULT 0,
                conditions TEXT NOT NULL DEFAULT '[]',
                patient_notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        db.commit()

# ---------------------------------------------------------------------------
# Simulated AI analysis engine
# ---------------------------------------------------------------------------

def simulate_dental_analysis(filename: str):
    seed = sum(ord(c) for c in filename) + int(time.time() * 1000) % 1000

    def rng(min_v, max_v, offset=0):
        val = ((seed * 9301 + 49297 + offset) % 233280) / 233280
        return round(min_v + val * (max_v - min_v), 1)

    cavity_conf    = rng(55, 95, 1)
    filling_conf   = rng(60, 97, 2)
    implant_conf   = rng(40, 92, 3)
    impacted_conf  = rng(50, 90, 4)

    cavity_det   = cavity_conf   > 68
    filling_det  = filling_conf  > 70
    implant_det  = implant_conf  > 75
    impacted_det = impacted_conf > 72

    def cavity_severity():
        if not cavity_det:   return "none"
        if cavity_conf >= 88: return "high"
        if cavity_conf >= 76: return "moderate"
        return "low"

    conditions = [
        {
            "name": "Dental Caries (Cavity)",
            "detected": cavity_det,
            "confidence": cavity_conf,
            "severity": cavity_severity(),
            "description": (
                f"Radiolucent lesion(s) detected indicating demineralization of enamel and dentin. "
                f"Confidence score indicates {'significant' if cavity_conf >= 80 else 'early-stage'} decay requiring clinical attention."
                if cavity_det else
                "No evidence of carious lesions detected. Enamel and dentin appear intact."
            ),
            "region": "Posterior molars (regions 16, 26, 36, 46)",
        },
        {
            "name": "Dental Filling (Restoration)",
            "detected": filling_det,
            "confidence": filling_conf,
            "severity": "none",
            "description": (
                f"Radiopaque restoration material detected, consistent with amalgam or composite filling. "
                f"Previous dental treatment identified in {'multiple' if filling_conf >= 85 else 'one or more'} tooth regions."
                if filling_det else
                "No pre-existing dental restorations detected in visible radiograph regions."
            ),
            "region": "Premolars and molars (regions 14, 24, 34, 44)",
        },
        {
            "name": "Dental Implant",
            "detected": implant_det,
            "confidence": implant_conf,
            "severity": "none",
            "description": (
                f"Metallic implant fixture detected with osseointegration characteristics. "
                f"Implant appears {'well-integrated' if implant_conf >= 82 else 'recently placed'} based on surrounding bone density."
                if implant_det else
                "No implant fixtures detected in the panoramic radiograph."
            ),
            "region": "Anterior/posterior edentulous areas",
        },
        {
            "name": "Impacted Tooth",
            "detected": impacted_det,
            "confidence": impacted_conf,
            "severity": ("high" if impacted_conf >= 82 else "moderate") if impacted_det else "none",
            "description": (
                f"Third molar (wisdom tooth) impaction detected. "
                f"Tooth angulation suggests {'complete bony impaction' if impacted_conf >= 82 else 'partial impaction'} "
                f"with potential risk to adjacent teeth."
                if impacted_det else
                "No impacted teeth detected. Third molars appear to have erupted normally or are absent."
            ),
            "region": "Third molar regions (18, 28, 38, 48)",
        },
    ]

    overall_conf = round(sum(c["confidence"] for c in conditions) / len(conditions), 1)
    found = sum(1 for c in conditions if c["detected"])
    return conditions, overall_conf, found

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route("/api/dental/analyses", methods=["GET"])
def list_analyses():
    db = get_db()
    rows = db.execute(
        "SELECT id, filename, status, overall_confidence, conditions_found, patient_notes, created_at "
        "FROM analyses ORDER BY id DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/dental/analyses", methods=["POST"])
def create_analysis():
    data = request.get_json()
    if not data or "imageBase64" not in data or "filename" not in data:
        return jsonify({"error": "imageBase64 and filename are required"}), 400

    conditions, overall_conf, found = simulate_dental_analysis(data["filename"])
    db = get_db()
    cur = db.execute(
        "INSERT INTO analyses (filename, image_base64, status, overall_confidence, conditions_found, conditions, patient_notes) "
        "VALUES (?, ?, 'completed', ?, ?, ?, ?)",
        (
            data["filename"],
            data["imageBase64"],
            overall_conf,
            found,
            json.dumps(conditions),
            data.get("patientNotes"),
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM analyses WHERE id = ?", (cur.lastrowid,)).fetchone()
    r = dict(row)
    r["conditions"] = json.loads(r["conditions"])
    return jsonify(r), 201


@app.route("/api/dental/analyses/<int:analysis_id>", methods=["GET"])
def get_analysis(analysis_id):
    db = get_db()
    row = db.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    r = dict(row)
    r["imageBase64"] = r.pop("image_base64")
    r["overallConfidence"] = r.pop("overall_confidence")
    r["conditionsFound"] = r.pop("conditions_found")
    r["patientNotes"] = r.pop("patient_notes")
    r["createdAt"] = r.pop("created_at")
    r["conditions"] = json.loads(r["conditions"])
    return jsonify(r)


@app.route("/api/dental/analyses/<int:analysis_id>", methods=["DELETE"])
def delete_analysis(analysis_id):
    db = get_db()
    row = db.execute("SELECT id FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    db.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
    db.commit()
    return "", 204


@app.route("/api/dental/stats", methods=["GET"])
def get_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    avg   = db.execute("SELECT AVG(overall_confidence) FROM analyses").fetchone()[0] or 0
    rows  = db.execute("SELECT conditions FROM analyses").fetchall()

    conditions_detected = cavities = implants = fillings = impacted = 0
    for r in rows:
        for c in json.loads(r["conditions"]):
            if c["detected"]:
                conditions_detected += 1
                name = c["name"].lower()
                if "caries" in name or "cavity" in name: cavities += 1
                elif "implant" in name:                   implants += 1
                elif "filling" in name or "restoration" in name: fillings += 1
                elif "impact" in name:                    impacted += 1

    return jsonify({
        "totalScans": total,
        "conditionsDetected": conditions_detected,
        "avgConfidence": round(avg, 1),
        "cavitiesFound": cavities,
        "implantsFound": implants,
        "fillingsFound": fillings,
        "impactedFound": impacted,
    })

# ---------------------------------------------------------------------------
# Frontend (single HTML page, embedded)
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Dental AI Diagnosis System</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }

  /* Layout */
  .layout { display: flex; min-height: 100vh; }
  .sidebar { width: 240px; background: #0a1628; border-right: 1px solid #1e3a5f; padding: 24px 16px; display: flex; flex-direction: column; gap: 8px; flex-shrink: 0; }
  .logo { font-size: 18px; font-weight: 700; color: #38bdf8; display: flex; align-items: center; gap: 8px; margin-bottom: 24px; }
  .logo-icon { width: 28px; height: 28px; background: #0ea5e9; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 14px; }
  .nav-btn { background: none; border: none; color: #94a3b8; padding: 10px 12px; border-radius: 8px; cursor: pointer; text-align: left; font-size: 14px; display: flex; align-items: center; gap: 10px; transition: all .15s; width: 100%; }
  .nav-btn:hover, .nav-btn.active { background: #1e3a5f; color: #38bdf8; }
  .main { flex: 1; padding: 32px; overflow-y: auto; }

  /* Cards */
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }
  .card-label { font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 8px; }
  .card-value { font-size: 28px; font-weight: 700; color: #f1f5f9; }
  .card-sub { font-size: 12px; color: #64748b; margin-top: 4px; }

  /* Page header */
  .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 28px; flex-wrap: wrap; gap: 12px; }
  .page-title { font-size: 26px; font-weight: 700; color: #f1f5f9; }
  .page-sub { font-size: 14px; color: #64748b; margin-top: 4px; }

  /* Buttons */
  .btn { display: inline-flex; align-items: center; gap: 8px; padding: 10px 18px; border-radius: 8px; border: none; cursor: pointer; font-size: 14px; font-weight: 600; transition: all .15s; }
  .btn-primary { background: #0ea5e9; color: #fff; }
  .btn-primary:hover { background: #38bdf8; }
  .btn-danger { background: transparent; color: #f87171; border: 1px solid #f87171; padding: 6px 10px; font-size: 12px; }
  .btn-danger:hover { background: #f8717122; }
  .btn-sm { padding: 6px 12px; font-size: 12px; }
  .btn-outline { background: transparent; border: 1px solid #334155; color: #94a3b8; }
  .btn-outline:hover { border-color: #38bdf8; color: #38bdf8; }

  /* Table */
  table { width: 100%; border-collapse: collapse; }
  th { font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; padding: 10px 16px; text-align: left; border-bottom: 1px solid #334155; }
  td { padding: 12px 16px; border-bottom: 1px solid #1e293b; font-size: 14px; vertical-align: middle; }
  tr:hover td { background: #1e293b44; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 99px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
  .badge-completed { background: #0ea5e920; color: #38bdf8; }
  .badge-high { background: #ef444420; color: #f87171; }
  .badge-moderate { background: #f59e0b20; color: #fbbf24; }
  .badge-low { background: #22c55e20; color: #4ade80; }
  .badge-none { background: #33415520; color: #64748b; }
  .link-btn { background: none; border: none; color: #38bdf8; cursor: pointer; font-size: 13px; text-decoration: underline; }

  /* Upload zone */
  .upload-zone { border: 2px dashed #334155; border-radius: 12px; padding: 60px 40px; text-align: center; cursor: pointer; transition: all .2s; }
  .upload-zone:hover, .upload-zone.drag { border-color: #0ea5e9; background: #0ea5e910; }
  .upload-icon { font-size: 48px; margin-bottom: 16px; opacity: .5; }
  .upload-title { font-size: 18px; font-weight: 600; color: #e2e8f0; margin-bottom: 8px; }
  .upload-sub { font-size: 14px; color: #64748b; }
  #file-input { display: none; }
  .preview-img { max-width: 100%; max-height: 500px; border-radius: 8px; border: 1px solid #334155; }

  /* Result layout */
  .result-grid { display: grid; grid-template-columns: 1fr 380px; gap: 24px; }
  @media (max-width: 900px) { .result-grid { grid-template-columns: 1fr; } }
  .condition-card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; margin-bottom: 12px; }
  .condition-card.high { border-left: 3px solid #f87171; }
  .condition-card.moderate { border-left: 3px solid #fbbf24; }
  .condition-card.low { border-left: 3px solid #4ade80; }
  .cond-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
  .cond-name { font-weight: 600; color: #f1f5f9; font-size: 14px; }
  .cond-conf { font-size: 20px; font-weight: 700; color: #38bdf8; }
  .cond-region { font-size: 12px; color: #64748b; margin-bottom: 8px; }
  .cond-desc { font-size: 13px; color: #94a3b8; line-height: 1.5; border-top: 1px solid #334155; padding-top: 8px; margin-top: 8px; }
  .progress { height: 6px; background: #1e293b; border-radius: 99px; overflow: hidden; margin: 6px 0; }
  .progress-bar { height: 100%; background: #0ea5e9; border-radius: 99px; transition: width .5s; }

  /* Summary card */
  .summary-card { background: #0c2340; border: 1px solid #1e3a5f; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
  .conf-big { font-size: 48px; font-weight: 800; color: #38bdf8; line-height: 1; }
  .conf-label { font-size: 13px; color: #64748b; margin-top: 4px; }
  .found-badge { background: #1e3a5f; padding: 10px 14px; border-radius: 8px; font-size: 14px; color: #94a3b8; margin-top: 12px; }
  .found-badge strong { color: #fbbf24; }

  /* Loading */
  .spinner { display: inline-block; width: 20px; height: 20px; border: 3px solid #334155; border-top-color: #0ea5e9; border-radius: 50%; animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loading-overlay { text-align: center; padding: 40px; }

  /* Toast */
  .toast { position: fixed; bottom: 24px; right: 24px; background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 14px 20px; color: #f1f5f9; font-size: 14px; box-shadow: 0 8px 32px #00000080; z-index: 999; transition: opacity .3s; }
  .toast.error { border-color: #f87171; color: #f87171; }
  .hidden { display: none; }
  .empty-state { text-align: center; padding: 60px 20px; color: #64748b; }
  .empty-icon { font-size: 48px; margin-bottom: 16px; opacity: .4; }
  .xray-viewer { background: #000; border-radius: 10px; padding: 4px; border: 1px solid #334155; }
  .xray-bar { background: #111; padding: 6px 12px; border-radius: 6px 6px 0 0; display: flex; justify-content: space-between; font-size: 11px; color: #475569; font-family: monospace; }
</style>
</head>
<body>
<div class="layout">
  <!-- Sidebar -->
  <nav class="sidebar">
    <div class="logo">
      <div class="logo-icon">&#9881;</div>
      Dental AI
    </div>
    <button class="nav-btn active" onclick="showPage('dashboard')" id="nav-dashboard">
      &#9632; Dashboard
    </button>
    <button class="nav-btn" onclick="showPage('analyze')" id="nav-analyze">
      &#8593; New Scan
    </button>
  </nav>

  <!-- Main content -->
  <main class="main" id="main-content"></main>
</div>

<!-- Toast -->
<div class="toast hidden" id="toast"></div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let currentPage = 'dashboard';
let selectedFile = null;
let selectedFileB64 = null;

// ── Toast ──────────────────────────────────────────────────────────────────
function toast(msg, isError=false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast' + (isError ? ' error' : '');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add('hidden'), 3500);
}

// ── Navigation ─────────────────────────────────────────────────────────────
function showPage(page, param=null) {
  currentPage = page;
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  const nb = document.getElementById('nav-' + (page === 'result' ? 'dashboard' : page));
  if (nb) nb.classList.add('active');
  if (page === 'dashboard')  renderDashboard();
  else if (page === 'analyze') renderAnalyze();
  else if (page === 'result')  renderResult(param);
}

// ── API helpers ────────────────────────────────────────────────────────────
async function api(path, opts={}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts
  });
  if (res.status === 204) return null;
  return res.json();
}

// ── Dashboard ──────────────────────────────────────────────────────────────
async function renderDashboard() {
  const main = document.getElementById('main-content');
  main.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';

  const [stats, analyses] = await Promise.all([
    api('/api/dental/stats'),
    api('/api/dental/analyses'),
  ]);

  main.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">Diagnostic Dashboard</div>
        <div class="page-sub">Overview of AI dental analyses and platform statistics.</div>
      </div>
      <button class="btn btn-primary" onclick="showPage('analyze')">+ New Scan</button>
    </div>

    <div class="stats-grid">
      <div class="card">
        <div class="card-label">Total Scans</div>
        <div class="card-value">${stats.totalScans}</div>
        <div class="card-sub">Processed by AI</div>
      </div>
      <div class="card">
        <div class="card-label">Avg. Confidence</div>
        <div class="card-value">${Number(stats.avgConfidence).toFixed(1)}%</div>
        <div class="card-sub">Model certainty</div>
      </div>
      <div class="card">
        <div class="card-label">Conditions Found</div>
        <div class="card-value">${stats.conditionsDetected}</div>
        <div class="card-sub">Across all scans</div>
      </div>
      <div class="card">
        <div class="card-label">Cavities Detected</div>
        <div class="card-value">${stats.cavitiesFound}</div>
        <div class="card-sub">Highest frequency condition</div>
      </div>
    </div>

    <div class="card">
      <div style="font-size:15px;font-weight:600;color:#e2e8f0;margin-bottom:4px;">Recent Analyses</div>
      <div style="font-size:13px;color:#64748b;margin-bottom:16px;">Latest OPG radiographs processed by the system.</div>
      ${analyses.length === 0 ? `
        <div class="empty-state">
          <div class="empty-icon">&#9685;</div>
          <div style="font-size:16px;font-weight:600;color:#e2e8f0;margin-bottom:8px;">No analyses found</div>
          <div style="margin-bottom:16px;">Upload an X-ray to see results here.</div>
          <button class="btn btn-primary" onclick="showPage('analyze')">Upload Scan</button>
        </div>
      ` : `
        <table>
          <thead><tr>
            <th>Filename</th><th>Date</th><th>Status</th><th>Conditions</th><th>Confidence</th><th>Actions</th>
          </tr></thead>
          <tbody>
            ${analyses.map(a => `
              <tr>
                <td style="color:#e2e8f0;font-weight:500;">${escHtml(a.filename)}</td>
                <td style="color:#94a3b8;">${fmtDate(a.created_at)}</td>
                <td><span class="badge badge-completed">${a.status}</span></td>
                <td style="color:#f1f5f9;font-weight:600;">${a.conditions_found}</td>
                <td style="color:#38bdf8;font-weight:600;">${Number(a.overall_confidence).toFixed(1)}%</td>
                <td style="display:flex;gap:8px;align-items:center;">
                  <button class="btn btn-sm btn-outline" onclick="showPage('result',${a.id})">View &rarr;</button>
                  <button class="btn btn-danger" onclick="deleteAnalysis(${a.id})">&#128465;</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `}
    </div>
  `;
}

async function deleteAnalysis(id) {
  await api('/api/dental/analyses/' + id, { method: 'DELETE' });
  toast('Analysis deleted');
  renderDashboard();
}

// ── Analyze page ───────────────────────────────────────────────────────────
function renderAnalyze() {
  selectedFile = null; selectedFileB64 = null;
  const main = document.getElementById('main-content');
  main.innerHTML = `
    <div class="page-header">
      <div>
        <div class="page-title">Upload X-Ray</div>
        <div class="page-sub">Upload a panoramic dental radiograph (OPG) for AI-powered diagnosis.</div>
      </div>
      <button class="btn btn-outline" onclick="showPage('dashboard')">&#8592; Dashboard</button>
    </div>

    <div class="card" style="max-width:720px;">
      <div class="upload-zone" id="drop-zone" onclick="document.getElementById('file-input').click()"
           ondragover="event.preventDefault();this.classList.add('drag')"
           ondragleave="this.classList.remove('drag')"
           ondrop="handleDrop(event)">
        <div class="upload-icon">&#9685;</div>
        <div class="upload-title">Drop your X-ray here</div>
        <div class="upload-sub">or click to browse &mdash; JPG, PNG, BMP, WEBP supported</div>
      </div>
      <input type="file" id="file-input" accept="image/*" onchange="handleFile(this.files[0])"/>

      <div id="preview-area" class="hidden" style="margin-top:20px;">
        <div class="xray-viewer">
          <div class="xray-bar">
            <span id="xray-filename">—</span>
            <span>VIEW: OPG RADIOGRAPH</span>
          </div>
          <img id="preview-img" class="preview-img" src="" alt="X-ray preview"/>
        </div>
        <div style="margin-top:16px;">
          <label style="font-size:13px;color:#94a3b8;display:block;margin-bottom:6px;">Clinical Notes (optional)</label>
          <textarea id="patient-notes" rows="3" placeholder="Add any relevant clinical observations..."
            style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#e2e8f0;padding:10px;font-size:13px;resize:vertical;"></textarea>
        </div>
        <button class="btn btn-primary" style="margin-top:16px;width:100%;" id="analyze-btn" onclick="runAnalysis()">
          Run AI Diagnosis
        </button>
      </div>
    </div>
  `;
}

function handleDrop(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.remove('drag');
  const f = e.dataTransfer.files[0];
  if (f) handleFile(f);
}

function handleFile(file) {
  if (!file || !file.type.startsWith('image/')) { toast('Please select an image file.', true); return; }
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    selectedFileB64 = e.target.result; // full data URL
    document.getElementById('preview-img').src = selectedFileB64;
    document.getElementById('xray-filename').textContent = file.name;
    document.getElementById('preview-area').classList.remove('hidden');
  };
  reader.readAsDataURL(file);
}

async function runAnalysis() {
  if (!selectedFile || !selectedFileB64) return;
  const btn = document.getElementById('analyze-btn');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Analyzing radiograph...';

  try {
    const result = await api('/api/dental/analyses', {
      method: 'POST',
      body: JSON.stringify({
        imageBase64: selectedFileB64,
        filename: selectedFile.name,
        patientNotes: document.getElementById('patient-notes').value || null,
      }),
    });
    toast('Analysis complete!');
    showPage('result', result.id);
  } catch (err) {
    toast('Analysis failed. Please try again.', true);
    btn.disabled = false;
    btn.innerHTML = 'Run AI Diagnosis';
  }
}

// ── Result page ────────────────────────────────────────────────────────────
async function renderResult(id) {
  const main = document.getElementById('main-content');
  main.innerHTML = '<div class="loading-overlay"><div class="spinner"></div><p style="margin-top:12px;color:#64748b;">Loading analysis...</p></div>';

  const a = await api('/api/dental/analyses/' + id);

  const severityOrder = { high: 0, moderate: 1, low: 2, none: 3 };
  const conds = [...a.conditions].sort((x, y) => severityOrder[x.severity] - severityOrder[y.severity]);

  main.innerHTML = `
    <div class="page-header">
      <div style="display:flex;align-items:center;gap:12px;">
        <button class="btn btn-outline btn-sm" onclick="showPage('dashboard')">&#8592;</button>
        <div>
          <div style="display:flex;align-items:center;gap:10px;">
            <span style="font-size:20px;font-weight:700;color:#f1f5f9;">${escHtml(a.filename)}</span>
            <span class="badge badge-completed">${a.status}</span>
          </div>
          <div style="font-size:13px;color:#64748b;margin-top:2px;">Processed on ${fmtDate(a.createdAt)}</div>
        </div>
      </div>
    </div>

    <div class="result-grid">
      <!-- Left: image -->
      <div>
        <div class="xray-viewer">
          <div class="xray-bar">
            <span>${escHtml(a.filename)}</span>
            <span style="color:#0ea5e9;">ENHANCED MODE</span>
          </div>
          <div style="background:#000;padding:12px;border-radius:0 0 8px 8px;min-height:300px;display:flex;align-items:center;justify-content:center;">
            <img src="${a.imageBase64}" alt="X-ray" style="max-width:100%;max-height:550px;object-fit:contain;"/>
          </div>
        </div>
        ${a.patientNotes ? `
          <div class="card" style="margin-top:16px;">
            <div style="font-size:12px;color:#64748b;font-weight:600;text-transform:uppercase;margin-bottom:8px;">Clinical Notes</div>
            <div style="font-size:14px;color:#94a3b8;">${escHtml(a.patientNotes)}</div>
          </div>` : ''}
      </div>

      <!-- Right: results -->
      <div>
        <div class="summary-card">
          <div style="font-size:12px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px;">Overall Confidence</div>
          <div class="conf-big">${Number(a.overallConfidence).toFixed(1)}%</div>
          <div class="progress" style="margin-top:12px;background:#1e3a5f;">
            <div class="progress-bar" style="width:${a.overallConfidence}%;background:#0ea5e9;"></div>
          </div>
          <div class="found-badge">
            <strong>${a.conditionsFound}</strong> condition(s) detected by AI model
          </div>
        </div>

        <div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px;">Detected Conditions</div>

        ${conds.map(c => `
          <div class="condition-card ${c.severity}">
            <div class="cond-header">
              <div>
                <div class="cond-name">${escHtml(c.name)}</div>
                <div class="cond-region">&#128205; ${escHtml(c.region)}</div>
                <span class="badge badge-${c.severity}" style="margin-top:4px;">${c.severity}</span>
              </div>
              <div style="text-align:right;">
                <div class="cond-conf">${Number(c.confidence).toFixed(1)}%</div>
                <div style="font-size:10px;color:#64748b;">conf.</div>
              </div>
            </div>
            <div class="progress">
              <div class="progress-bar" style="width:${c.confidence}%;background:${c.detected ? '#0ea5e9' : '#334155'};"></div>
            </div>
            <div class="cond-desc">${escHtml(c.description)}</div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

// ── Utilities ──────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fmtDate(s) {
  try { return new Date(s + (s.includes('T') ? '' : 'Z')).toLocaleString(); }
  catch { return s; }
}

// Boot
showPage('dashboard');
</script>
</body>
</html>
"""

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    # Only serve frontend for non-API routes
    if path.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    return HTML, 200, {"Content-Type": "text/html"}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    print("\n" + "="*50)
    print("  Dental AI Diagnosis System")
    print("="*50)
    print("  Open http://localhost:5000 in your browser")
    print("  Press Ctrl+C to stop")
    print("="*50 + "\n")
    app.run(debug=False, host="0.0.0.0", port=5000)
