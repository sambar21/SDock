import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { anyActive, formatBytes, reductionText, statusLabel, statusMessage } from "./scan-state.js";

const API = "/api/v1";
const POLL_MS = 2000;

const $ = (id) => document.getElementById(id);

// sessionStorage can be blocked, so every use is guarded.
function remember(key, value) {
  try {
    if (value == null) sessionStorage.removeItem(key);
    else sessionStorage.setItem(key, value);
  } catch {}
}
function recall(key) {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

const state = {
  token: recall("token"),
  email: recall("email"),
  orgs: [],
  org: null,
  scans: [],
  selectedId: null,
  shownModelFor: null,
  pollTimer: null,
};

class ApiFailure extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function api(path, { method = "GET", json, form, raw = false } = {}) {
  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  let body;
  if (json) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }
  const response = await fetch(API + path, { method, headers, body });
  if (response.status === 401 && state.token) {
    signOut("Your session expired. Please sign in again.");
    throw new ApiFailure(401, "Signed out.");
  }
  if (!response.ok) {
    let message = response.statusText;
    try {
      message = (await response.json()).message || message;
    } catch {
      // Not our JSON. A host in front of the API (such as Vercel) may have refused the upload itself.
      if (response.status === 413) message = "That file is too large for this deployment.";
    }
    throw new ApiFailure(response.status, message);
  }
  if (raw) return response;
  return response.status === 204 ? null : response.json();
}

function show(element, visible) {
  element.classList.toggle("hidden", !visible);
}

// ---------- Sign in ----------

function renderSignedIn() {
  const signedIn = Boolean(state.token);
  show($("auth-card"), !signedIn);
  show($("app"), signedIn);
  show($("sign-out"), signedIn);
  show($("whoami"), signedIn);
  $("whoami").textContent = state.email || "";
}

function signOut(message = "") {
  state.token = null;
  state.email = null;
  state.org = null;
  state.scans = [];
  state.selectedId = null;
  clearTimeout(state.pollTimer);
  remember("token", null);
  remember("email", null);
  clearModel();
  renderSignedIn();
  $("auth-error").textContent = message;
}

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const kind = event.submitter?.dataset.kind || "login";
  $("auth-error").textContent = "";
  const email = $("email").value.trim();
  try {
    const result = await api(`/auth/${kind}`, { method: "POST", json: { email, password: $("password").value } });
    state.token = result.access_token;
    state.email = email.toLowerCase();
    remember("token", state.token);
    remember("email", state.email);
    $("password").value = "";
    renderSignedIn();
    await loadOrgs();
  } catch (error) {
    $("auth-error").textContent = error.message;
  }
});

$("sign-out").addEventListener("click", () => signOut());

// ---------- Organizations ----------

async function loadOrgs(selectId) {
  $("org-error").textContent = "";
  try {
    state.orgs = await api("/orgs");
  } catch (error) {
    if (error.status !== 401) $("org-error").textContent = error.message;
    return;
  }
  const select = $("org-select");
  select.replaceChildren(
    ...state.orgs.map((org) => {
      const option = document.createElement("option");
      option.value = org.id;
      option.textContent = `${org.name} (${org.your_role})`;
      return option;
    }),
  );
  const wanted = selectId || recall("org");
  const chosen = state.orgs.find((org) => org.id === wanted) || state.orgs[0] || null;
  if (chosen) select.value = chosen.id;
  await chooseOrg(chosen);
}

async function chooseOrg(org) {
  state.org = org;
  state.scans = [];
  state.selectedId = null;
  clearTimeout(state.pollTimer);
  remember("org", org?.id ?? null);
  show($("upload-card"), Boolean(org) && org.your_role !== "viewer");
  renderList();
  renderDetail();
  if (org) await refreshScans();
}

$("org-select").addEventListener("change", (event) => {
  chooseOrg(state.orgs.find((org) => org.id === event.target.value) || null);
});

$("org-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = $("org-name").value.trim();
  if (!name) return;
  $("org-error").textContent = "";
  try {
    const created = await api("/orgs", { method: "POST", json: { name } });
    $("org-name").value = "";
    await loadOrgs(created.id);
  } catch (error) {
    $("org-error").textContent = error.message;
  }
});

// ---------- Scans ----------

async function refreshScans() {
  clearTimeout(state.pollTimer);
  if (!state.org) return;
  const orgId = state.org.id;
  try {
    const scans = await api(`/orgs/${orgId}/scans?limit=200`);
    if (state.org?.id !== orgId) return; // switched organizations while waiting
    state.scans = scans;
    $("list-error").textContent = "";
  } catch (error) {
    if (error.status !== 401) $("list-error").textContent = error.message;
  }
  renderList();
  renderDetail();
  if (anyActive(state.scans)) state.pollTimer = setTimeout(refreshScans, POLL_MS);
}

function badge(element, status) {
  element.className = `badge ${status}`;
  element.textContent = statusLabel(status);
}

function renderList() {
  const list = $("scan-list");
  show($("list-empty"), Boolean(state.org) && state.scans.length === 0);
  list.replaceChildren(
    ...state.scans.map((scan) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      if (scan.id === state.selectedId) button.setAttribute("aria-current", "true");

      const name = document.createElement("span");
      name.className = "scan-name";
      name.textContent = scan.name;
      const status = document.createElement("span");
      badge(status, scan.status);
      const meta = document.createElement("span");
      meta.className = "scan-meta";
      meta.textContent = new Date(scan.created_at).toLocaleString();

      button.append(name, status, meta);
      button.addEventListener("click", () => {
        state.selectedId = scan.id;
        renderList();
        renderDetail();
      });
      item.append(button);
      return item;
    }),
  );
}

$("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("file").files[0];
  if (!file || !state.org) return;
  const form = new FormData();
  form.append("file", file);
  if ($("scan-name").value.trim()) form.append("name", $("scan-name").value.trim());

  const button = $("upload-button");
  button.disabled = true;
  button.textContent = "Uploading...";
  $("upload-error").textContent = "";
  try {
    const scan = await api(`/orgs/${state.org.id}/scans`, { method: "POST", form });
    $("upload-form").reset();
    state.selectedId = scan.id;
    await refreshScans();
  } catch (error) {
    $("upload-error").textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "Upload";
  }
});

$("delete-button").addEventListener("click", async () => {
  const scan = selectedScan();
  if (!scan || !confirm(`Delete "${scan.name}"? This cannot be undone.`)) return;
  try {
    await api(`/scans/${scan.id}`, { method: "DELETE" });
    state.selectedId = null;
    await refreshScans();
  } catch (error) {
    $("list-error").textContent = error.message;
  }
});

// ---------- Detail and 3D stage ----------

const selectedScan = () => state.scans.find((scan) => scan.id === state.selectedId) || null;

function setStageMessage(text) {
  $("stage-message").textContent = text;
  show($("stage-message"), Boolean(text));
}

function renderDetail() {
  const scan = selectedScan();
  show($("detail-empty"), !scan);
  show($("detail-body"), Boolean(scan));
  if (!scan) {
    clearModel();
    return;
  }

  $("detail-name").textContent = scan.name;
  badge($("detail-badge"), scan.status);
  show($("delete-button"), state.org?.your_role !== "viewer");

  const parts = [`Original ${formatBytes(scan.original_size)}`];
  if (scan.preview_size != null) parts.push(`preview ${formatBytes(scan.preview_size)}`);
  const reduction = reductionText(scan);
  if (reduction) parts.push(reduction);
  $("detail-info").textContent = parts.join(" - ");

  if (scan.status === "ready") {
    if (state.shownModelFor !== scan.id) loadModel(scan.id);
  } else {
    clearModel();
    setStageMessage(statusMessage(scan));
  }
}

let three = null;

function ensureStage() {
  if (three) return three;
  const stage = $("stage");
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true });
  } catch {
    return null;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  stage.prepend(renderer.domElement);

  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x444455, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(3, 5, 4);
  scene.add(sun);

  const camera = new THREE.PerspectiveCamera(50, 1, 0.01, 1000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  const resize = () => {
    const { clientWidth: width, clientHeight: height } = stage;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(stage);
  resize();

  renderer.setAnimationLoop(() => {
    controls.update();
    renderer.render(scene, camera);
  });

  three = { renderer, scene, camera, controls, model: null };
  return three;
}

function clearModel() {
  state.shownModelFor = null;
  if (!three?.model) return;
  three.scene.remove(three.model);
  three.model.traverse((node) => {
    node.geometry?.dispose();
    node.material?.dispose();
  });
  three.model = null;
}

function frame(stage, model) {
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  const radius = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 0.001);
  const distance = radius / Math.sin(THREE.MathUtils.degToRad(stage.camera.fov / 2));
  stage.camera.near = radius / 100;
  stage.camera.far = radius * 100;
  stage.camera.position.copy(center).add(new THREE.Vector3(1, 0.7, 1).normalize().multiplyScalar(distance));
  stage.camera.updateProjectionMatrix();
  stage.controls.target.copy(center);
  stage.controls.update();
}

async function loadModel(scanId) {
  clearModel();
  state.shownModelFor = scanId;
  setStageMessage("Loading the 3D preview...");
  const stage = ensureStage();
  if (!stage) {
    setStageMessage("This browser cannot show 3D graphics (WebGL is unavailable).");
    return;
  }
  try {
    const response = await api(`/scans/${scanId}/preview`, { raw: true });
    const bytes = await response.arrayBuffer();
    if (state.shownModelFor !== scanId) return; // another scan was picked meanwhile
    const gltf = await new GLTFLoader().parseAsync(bytes, "");
    if (state.shownModelFor !== scanId) return;

    gltf.scene.traverse((node) => {
      if (node.isPoints) {
        node.material.size = 2;
        node.material.sizeAttenuation = false;
      } else if (node.isMesh) {
        if (!node.geometry.attributes.normal) node.geometry.computeVertexNormals();
        node.material.side = THREE.DoubleSide;
      }
    });
    stage.model = gltf.scene;
    stage.scene.add(gltf.scene);
    frame(stage, gltf.scene);
    setStageMessage("");
  } catch (error) {
    if (state.shownModelFor !== scanId) return;
    state.shownModelFor = null;
    const denied = error.status === 403 || error.status === 404;
    setStageMessage(denied ? "You do not have access to this scan." : `Could not load the preview: ${error.message}`);
  }
}

// ---------- Start ----------

renderSignedIn();
if (state.token) loadOrgs();
