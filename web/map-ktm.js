// Kathmandu Ring Road (the whole 27 km loop) for the driving page.
// Inlined into drive.html by web/make_drive.py at the "@@map" marker, so it
// shares the page's module scope (THREE, CANNON, scene, world, bus, T, ...).
// Data: ktm_map.json from world/export_web.py (OpenStreetMap, Google Open
// Buildings, Copernicus DEM, Sentinel-2). Map x = east, y = north; three.js
// X = x, Z = -y. The playable world is flat; hills rise away from the road.
// The road is cut into 200 m chunks; chunks near the bus are built (meshes and
// colliders) and far ones are thrown away, so the whole loop never sits in
// memory at once. Traffic drives on the left around the bus.
const KTM = { ready: false, start: null, lights: [], stream: () => {}, update: () => {} };
const ktmNight = () => (T ? T.night : 0);
// Collider streaming: thousands of static bodies make every physics step
// scan them all, so only those within ~100 m of the bus are in the world.
const KTM_CELL = 50, KTM_REACH = 2;
const ktmCells = new Map(), ktmActive = new Set();
let ktmOwner = null;                 // chunk collecting the bodies being made
function poolAdd(b) {
  b.aabbNeedsUpdate = true;          // placed after the shape was added: the cached bounds are stale
  const key = Math.floor(b.position.x / KTM_CELL) + ',' + Math.floor(b.position.z / KTM_CELL);
  if (!ktmCells.has(key)) ktmCells.set(key, new Set());
  ktmCells.get(key).add(b);
  b.ktmKey = key;
  if (ktmOwner) ktmOwner.push(b);
}
function poolDrop(b) {
  const set = ktmCells.get(b.ktmKey);
  if (set) set.delete(b);
  if (ktmActive.has(b)) { world.removeBody(b); ktmActive.delete(b); }
}
function poolBox(half, pos, yaw = 0) {
  const b = new CANNON.Body({ mass: 0, shape: new CANNON.Box(new CANNON.Vec3(...half)) });
  b.position.set(...pos); b.quaternion.setFromEuler(0, yaw, 0); poolAdd(b);
}
function poolBoxP(half, pos, yaw, pitch) {         // yawed, then tilted along its length (ramps)
  const b = new CANNON.Body({ mass: 0, shape: new CANNON.Box(new CANNON.Vec3(...half)) });
  b.position.set(...pos);
  b.quaternion.setFromAxisAngle(new CANNON.Vec3(0, 1, 0), yaw).mult(new CANNON.Quaternion().setFromAxisAngle(new CANNON.Vec3(0, 0, 1), pitch), b.quaternion);
  poolAdd(b);
}
function poolCyl(r, h, pos) {
  const b = new CANNON.Body({ mass: 0, shape: new CANNON.Cylinder(r, r, h, 8) });
  b.position.set(...pos); poolAdd(b);
}
let ktmLastCell = null;
function poolStream(x, z) {
  const cx = Math.floor(x / KTM_CELL), cz = Math.floor(z / KTM_CELL), key = cx + ',' + cz;
  if (key === ktmLastCell) return;
  ktmLastCell = key;
  const want = new Set();
  for (let i = -KTM_REACH; i <= KTM_REACH; i++) for (let j = -KTM_REACH; j <= KTM_REACH; j++) {
    const list = ktmCells.get((cx + i) + ',' + (cz + j));
    if (list) for (const b of list) want.add(b);
  }
  for (const b of ktmActive) if (!want.has(b)) { world.removeBody(b); ktmActive.delete(b); }
  for (const b of want) if (!ktmActive.has(b)) { world.addBody(b); ktmActive.add(b); }
}
{
  const P2 = (x, y, h = 0) => new THREE.Vector3(x, h, -y);
  const tex = (w, h, draw, rep = true) => {
    const c = document.createElement('canvas'); c.width = w; c.height = h;
    draw(c.getContext('2d'), w, h);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    if (rep) t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.anisotropy = MAX_ANISO;
    return t;
  };
  const noisy = (g, w, h, base, spread, n) => {
    g.fillStyle = base; g.fillRect(0, 0, w, h);
    for (let i = 0; i < n; i++) {
      const v = Math.random() * spread - spread / 2;
      g.fillStyle = `rgba(${v > 0 ? 255 : 0},${v > 0 ? 255 : 0},${v > 0 ? 255 : 0},${Math.abs(v)})`;
      g.fillRect(Math.random() * w, Math.random() * h, 1 + Math.random() * 2, 1 + Math.random() * 2);
    }
  };
  // --- materials (worn asphalt, kerbs, pavers, house walls, shutters) ---------
  const asphaltTex = tex(256, 256, (g, w, h) => {
    noisy(g, w, h, '#3b3d40', 0.22, 9000);
    for (let i = 0; i < 18; i++) {           // patches and oil stains
      const x = Math.random() * w, y = Math.random() * h, r = 10 + Math.random() * 40;
      const gr = g.createRadialGradient(x, y, 0, x, y, r);
      gr.addColorStop(0, `rgba(${Math.random() < 0.5 ? '25,25,27' : '110,108,104'},0.25)`); gr.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = gr; g.fillRect(x - r, y - r, 2 * r, 2 * r);
    }
    g.strokeStyle = 'rgba(20,20,22,0.55)'; g.lineWidth = 1;
    for (let i = 0; i < 10; i++) {           // cracks
      let x = Math.random() * w, y = Math.random() * h, a = Math.random() * 6.3;
      g.beginPath(); g.moveTo(x, y);
      for (let k = 0; k < 12; k++) { a += (Math.random() - 0.5); x += Math.cos(a) * 5; y += Math.sin(a) * 5; g.lineTo(x, y); }
      g.stroke();
    }
  });
  const asphalt = new THREE.MeshStandardMaterial({ map: asphaltTex, roughness: 0.92 });
  const kerbTex = tex(64, 8, (g) => { g.fillStyle = '#e0a521'; g.fillRect(0, 0, 32, 8); g.fillStyle = '#111'; g.fillRect(32, 0, 32, 8); });
  const kerb = new THREE.MeshStandardMaterial({ map: kerbTex, roughness: 0.6, side: THREE.DoubleSide });
  const paverTex = tex(128, 128, (g, w, h) => {
    g.fillStyle = '#6b625a'; g.fillRect(0, 0, w, h);
    for (let y = 0; y < 8; y++) for (let x = 0; x < 4; x++) {
      const v = 120 + Math.random() * 40;
      g.fillStyle = `rgb(${v},${v * 0.86},${v * 0.78})`;
      g.fillRect(x * 32 + (y % 2) * 16 + 1, y * 16 + 1, 30, 14);
    }
  });
  const pavers = new THREE.MeshStandardMaterial({ map: paverTex, roughness: 0.85 });
  const medianMat = new THREE.MeshStandardMaterial({ map: tex(64, 64, (g, w, h) => noisy(g, w, h, '#4a4535', 0.4, 900)), roughness: 0.95 });
  const vergeMat = new THREE.MeshStandardMaterial({ map: tex(64, 64, (g, w, h) => noisy(g, w, h, '#4f5a2c', 0.4, 900)), roughness: 1 });
  const yellow = new THREE.MeshStandardMaterial({ color: 0xd6a22a, roughness: 0.55 });
  const whiteP = new THREE.MeshStandardMaterial({ color: 0xdcdcd4, roughness: 0.55 });
  const rail = new THREE.MeshStandardMaterial({ color: 0x8c8a84, roughness: 0.7, side: THREE.DoubleSide });
  const concrete = new THREE.MeshStandardMaterial({ color: 0xa29e95, roughness: 0.9, side: THREE.DoubleSide });
  // one bay of a Kathmandu house: 3.1 m wide, 2.9 m storey, window + slab band
  const bayTex = tex(128, 128, (g, w, h) => {
    noisy(g, w, h, '#ffffff', 0.12, 600);
    g.fillStyle = 'rgba(0,0,0,0.12)'; g.fillRect(0, h - 9, w, 9);               // slab band
    g.fillStyle = '#e8e6e0'; g.fillRect(28, 26, 72, 62);                           // frame
    g.fillStyle = '#1b2530'; g.fillRect(33, 31, 62, 52);                           // glass
    g.fillStyle = 'rgba(255,255,255,0.18)'; g.fillRect(33, 31, 62, 7);
    g.fillStyle = '#d8d6cf'; g.fillRect(63, 31, 3, 52);                            // mullion
  });
  const walls = new THREE.MeshStandardMaterial({ map: bayTex, vertexColors: true, roughness: 0.85 });
  const shutterTex = tex(64, 64, (g, w, h) => {
    for (let y = 0; y < h; y += 4) { g.fillStyle = y % 8 ? '#6d7b88' : '#56626d'; g.fillRect(0, y, w, 4); }
    g.fillStyle = '#2b3036'; g.fillRect(0, 0, 2, h);
  });
  const shutters = new THREE.MeshStandardMaterial({ map: shutterTex, roughness: 0.5, metalness: 0.4 });
  const roofMat = new THREE.MeshStandardMaterial({ color: 0x77736c, roughness: 0.95 });
  const colMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.7, side: THREE.DoubleSide });
  const tankGeo = new THREE.CylinderGeometry(0.6, 0.6, 1.25, 14), tankMat = new THREE.MeshStandardMaterial({ color: 0x0b0b0c, roughness: 0.4 });
  const farGeo = new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0), farMat = new THREE.MeshStandardMaterial({ roughness: 0.9 });
  const trunkGeo = new THREE.CylinderGeometry(0.14, 0.22, 2.4, 7).translate(0, 1.2, 0), trunkMat = new THREE.MeshStandardMaterial({ color: 0x5b4632, roughness: 1 });
  const wireMat = new THREE.LineBasicMaterial({ color: 0x111111 });
  const shared = new Set([tankGeo, farGeo, trunkGeo, broad.geometry]);
  const WALL_COLS = ['#d9d4c7', '#c9b28a', '#e9e7df', '#8a3b2a', '#d79a8f', '#8fb3d1', '#e3c35c', '#cf7c45', '#a8c39a', '#bba0c4', '#7f9dbd', '#a64a35', '#f0e6c8']
    .map(c => new THREE.Color(c));
  const SIGN_COLS = ['#b5121b', '#123a8f', '#e0a800', '#0f7a35', '#f2f2ee', '#7a0f4d'];
  const SHOP_NAMES = ['किराना पसल', 'मेडिकल हल', 'मोबाइल सेन्टर', 'हार्डवेयर', 'फेन्सी स्टोर', 'होटल तथा लज', 'खाजा घर',
    'टायर पसल', 'बैंक लिमिटेड', 'सैलुन', 'कपडा पसल', 'अटो पार्ट्स', 'मिठाई पसल', 'स्टेशनरी', 'इलेक्ट्रिकल्स', 'ज्वेलर्स'];
  const signMats = [];
  function drawSign(c, i) {
    const g = c.getContext('2d'), bg = SIGN_COLS[i % SIGN_COLS.length];
    g.fillStyle = bg; g.fillRect(0, 0, c.width, c.height);
    g.fillStyle = bg === '#f2f2ee' || bg === '#e0a800' ? '#1a1a1a' : '#ffffff';
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.font = '800 44px Mukta, "Noto Sans Devanagari", sans-serif';
    g.fillText(SHOP_NAMES[i % SHOP_NAMES.length], c.width / 2, c.height / 2 + 3);
  }
  const redraw = new Set();     // canvases to redraw once the web fonts arrive
  for (let i = 0; i < 16; i++) {
    const c = document.createElement('canvas'); c.width = 512; c.height = 72; drawSign(c, i);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = MAX_ANISO;
    redraw.add(() => { drawSign(c, i); t.needsUpdate = true; });
    signMats.push(new THREE.MeshStandardMaterial({ map: t, roughness: 0.5 }));
  }
  let fontsReady = false;
  document.fonts && document.fonts.ready.then(() => { fontsReady = true; redraw.forEach(f => f()); });

  // --- geometry helpers -----------------------------------------------------
  class Geo {               // growable position/uv/color/index arrays
    constructor() { this.p = []; this.uv = []; this.c = []; this.i = []; }
    quad(a, b, c, d, ua, ub, uc, ud, col) {
      const n = this.p.length / 3;
      for (const v of [a, b, c, d]) this.p.push(v.x, v.y, v.z);
      for (const u of [ua, ub, uc, ud]) this.uv.push(u[0], u[1]);
      if (col) for (let k = 0; k < 4; k++) this.c.push(col.r, col.g, col.b);
      this.i.push(n, n + 1, n + 2, n, n + 2, n + 3);
    }
    box(cx, cy, cz, ax, az, hx, hy, hz, col) {   // ax/az: unit vectors (x,z) of the box's local X and Z
      const corner = (sx, sy, sz) => new THREE.Vector3(cx + ax[0] * hx * sx + az[0] * hz * sz, cy + hy * sy, cz + ax[1] * hx * sx + az[1] * hz * sz);
      const F = [[[-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], [[1, -1, -1], [-1, -1, -1], [-1, 1, -1], [1, 1, -1]],
        [[1, -1, 1], [1, -1, -1], [1, 1, -1], [1, 1, 1]], [[-1, -1, -1], [-1, -1, 1], [-1, 1, 1], [-1, 1, -1]],
        [[-1, 1, 1], [1, 1, 1], [1, 1, -1], [-1, 1, -1]], [[-1, -1, -1], [1, -1, -1], [1, -1, 1], [-1, -1, 1]]];
      for (const f of F) this.quad(...f.map(v => corner(...v)), [0, 0], [1, 0], [1, 1], [0, 1], col);
    }
    wheel(cx, cy, cz, r, w, col, n = 10) {        // a wheel turning about the local Z axis
      const hub = col.clone().multiplyScalar(2.2);
      for (let i = 0; i < n; i++) {
        const a0 = i / n * Math.PI * 2, a1 = (i + 1) / n * Math.PI * 2;
        const p = (a, z) => new THREE.Vector3(cx + Math.cos(a) * r, cy + Math.sin(a) * r, cz + z);
        this.quad(p(a0, -w / 2), p(a1, -w / 2), p(a1, w / 2), p(a0, w / 2), [0, 0], [1, 0], [1, 1], [0, 1], col);
        for (const z of [-w / 2, w / 2]) {
          const m = this.p.length / 3, c = new THREE.Vector3(cx, cy, cz + z);
          for (const v of [c, p(a0, z), p(a1, z)]) { this.p.push(v.x, v.y, v.z); this.uv.push(0, 0); this.c.push(hub.r, hub.g, hub.b); }
          if (z > 0) this.i.push(m, m + 1, m + 2); else this.i.push(m, m + 2, m + 1);
        }
      }
    }
    get empty() { return this.i.length === 0; }
    geometry() {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(this.p, 3));
      g.setAttribute('uv', new THREE.Float32BufferAttribute(this.uv, 2));
      if (this.c.length) g.setAttribute('color', new THREE.Float32BufferAttribute(this.c, 3));
      g.setIndex(this.i);
      g.computeVertexNormals();
      return g;
    }
    mesh(mat, group, shadow = true) {
      if (this.empty) return null;
      const m = new THREE.Mesh(this.geometry(), mat);
      m.castShadow = shadow; m.receiveShadow = true;
      group.add(m);
      return m;
    }
  }

  function build(D) {
    const r = D.road;
    const M0 = r.median / 2, CW = 2 * r.lane + r.shoulder, I1 = M0 + CW, FOOT = r.foot, LOOP = r.loop;
    const pts = [];
    for (let k = 0; k < r.pts.length; k += 2) pts.push([r.pts[k], r.pts[k + 1]]);
    const n = pts.length, S = [0], TG = [], N = [];
    for (let k = 1; k < n; k++) S.push(S[k - 1] + Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]));
    const W = r.wide.map(v => v / 20);                       // 1 = 8 lanes, 0 = 4 lanes
    const wrap = k => ((k % n) + n) % n;
    for (let k = 0; k < n; k++) {
      const a = pts[wrap(k - 1)], b = pts[wrap(k + 1)];
      const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
      TG.push([(b[0] - a[0]) / L, (b[1] - a[1]) / L]); N.push([-TG[k][1], TG[k][0]]);
    }
    // cross-section at point k (distances from the centreline)
    const S1 = k => I1 + r.sep * W[wrap(k)];                 // outer carriageway starts
    const EDGE = k => S1(k) + CW * W[wrap(k)];               // outer kerb line
    const at = (k, o, h) => { k = wrap(k); return P2(pts[k][0] + N[k][0] * o, pts[k][1] + N[k][1] * o, h); };
    const sOf = k => k >= n ? LOOP + S[k - n] : S[k];
    // point at distance s (wraps) and offset o
    const kAt = s => { s = ((s % LOOP) + LOOP) % LOOP; let lo = 0, hi = n - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (S[m] <= s) lo = m; else hi = m - 1; } return lo; };
    const frame = s => {
      s = ((s % LOOP) + LOOP) % LOOP;
      const k = kAt(s), k2 = wrap(k + 1), seg = sOf(k + 1) - S[k], f = seg > 0 ? (s - S[k]) / seg : 0;
      return { k, f, x: pts[k][0] + (pts[k2][0] - pts[k][0]) * f, y: pts[k][1] + (pts[k2][1] - pts[k][1]) * f,
        tx: TG[k][0] + (TG[k2][0] - TG[k][0]) * f, ty: TG[k][1] + (TG[k2][1] - TG[k][1]) * f, w: W[k] + (W[k2] - W[k]) * f };
    };
    const inBridge = s => r.bridges.some(([a, b]) => s >= a && s <= b);
    // flyover (Gwarko - Balkumari): the inner carriageways climb onto a deck; OSM's bridge
    // ways are the elevated part, with 150 m ramps beyond each end
    const FLY_H = 6.8, RAMP = 150;
    const flyH = s => {
      s = ((s % LOOP) + LOOP) % LOOP;
      for (const [a, b] of r.flyovers || []) {
        if (s <= a - RAMP || s >= b + RAMP) continue;
        const t = s < a ? (s - (a - RAMP)) / RAMP : s > b ? (b + RAMP - s) / RAMP : 1;
        return FLY_H * t * t * (3 - 2 * t);
      }
      return 0;
    };

    // --- where am I: spatial hash of the centreline --------------------------------
    const HC = 40, hash = new Map();
    pts.forEach((p, k) => {
      const key = Math.floor(p[0] / HC) + ',' + Math.floor(p[1] / HC);
      if (!hash.has(key)) hash.set(key, []);
      hash.get(key).push(k);
    });
    function locate(x, y, wide = false) {        // nearest centreline point, signed offset, distance along
      const cx = Math.floor(x / HC), cy = Math.floor(y / HC);
      let best = -1, bd = 1e18;
      const R = wide ? 3 : 1;
      for (let i = -R; i <= R; i++) for (let j = -R; j <= R; j++) {
        const list = hash.get((cx + i) + ',' + (cy + j));
        if (list) for (const k of list) { const d = (pts[k][0] - x) ** 2 + (pts[k][1] - y) ** 2; if (d < bd) { bd = d; best = k; } }
      }
      if (best < 0) {
        if (!wide) return locate(x, y, true);
        for (let k = 0; k < n; k++) { const d = (pts[k][0] - x) ** 2 + (pts[k][1] - y) ** 2; if (d < bd) { bd = d; best = k; } }
      }
      const dx = x - pts[best][0], dy = y - pts[best][1];
      const along = dx * TG[best][0] + dy * TG[best][1];
      return { k: best, o: dx * N[best][0] + dy * N[best][1], s: ((S[best] + along) % LOOP + LOOP) % LOOP, d: Math.sqrt(bd) };
    }
    KTM.locate = locate; KTM.frame = s => frame(s);

    // --- side roads: gaps in the footpath where they join, and on-road test points -------
    const gap = [new Uint8Array(n), new Uint8Array(n)];       // [left side, right side]
    const stubHash = new Map();
    for (const st of D.stubs) {
      const sideI = st.side > 0 ? 0 : 1, half = Math.ceil((st.w / 2 + 2) / r.step);
      for (let d = -half; d <= half; d++) gap[sideI][wrap(st.k + d)] = 1;
      for (let k = 0; k < st.p.length; k += 2) {
        const key = Math.floor(st.p[k] / HC) + ',' + Math.floor(st.p[k + 1] / HC);
        if (!stubHash.has(key)) stubHash.set(key, []);
        stubHash.get(key).push([st.p[k], st.p[k + 1], st.w / 2 + 0.8]);
      }
    }
    const isGap = (sg, k) => gap[sg > 0 ? 0 : 1][wrap(k)] === 1;
    BUS.onRoad = (x, z) => {
      const y = -z, L = locate(x, y);
      if (Math.abs(L.o) <= EDGE(L.k) + 0.2) return true;
      if (isGap(Math.sign(L.o), L.k) && Math.abs(L.o) <= EDGE(L.k) + FOOT + 1) return true;
      const list = stubHash.get(Math.floor(x / HC) + ',' + Math.floor(y / HC));
      return !!list && list.some(([px, py, hw]) => (px - x) ** 2 + (py - y) ** 2 < hw * hw);
    };

    // --- place boards: each place named on both carriageways, plus the next places ahead ---
    const places = D.places.map(p => ({ ...p, s: S[p.k] }));
    function boardMat(draw, w, h) {
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = MAX_ANISO;
      const f = () => { draw(c.getContext('2d'), w, h); t.needsUpdate = true; };
      f();
      const m = new THREE.MeshStandardMaterial({ map: t, roughness: 0.45, emissive: 0xffffff, emissiveMap: t, emissiveIntensity: 0.12 });
      if (!fontsReady) { redraw.add(f); m.userData.redraw = f; }
      return m;
    }
    const frameBoard = (g, w, h, bg) => {
      g.fillStyle = bg; g.fillRect(0, 0, w, h);
      g.strokeStyle = '#ffffff'; g.lineWidth = 8; g.strokeRect(12, 12, w - 24, h - 24);
      g.fillStyle = '#ffffff'; g.textAlign = 'center'; g.textBaseline = 'middle';
    };
    const nameMats = places.map(p => boardMat((g, w, h) => {
      frameBoard(g, w, h, '#0b4fa3');
      g.font = '800 104px Mukta, "Noto Sans Devanagari", sans-serif'; g.fillText(p.ne, w / 2, h * 0.37);
      g.font = '700 64px Oswald, Mukta, sans-serif'; g.fillText(p.en.toUpperCase(), w / 2, h * 0.76);
    }, 768, 320));
    const km = d => d < 1000 ? (Math.round(d / 100) * 100) + ' m' : (d / 1000).toFixed(1) + ' km';
    // direction board for travel direction dir (+1 = increasing s): the next two places
    const aheadOf = (s, dir) => places.map(p => ({ p, d: ((dir > 0 ? p.s - s : s - p.s) % LOOP + LOOP) % LOOP }))
      .filter(q => q.d > 40).sort((a, b) => a.d - b.d).slice(0, 2);
    function dirMat(s, dir) {
      const list = aheadOf(s, dir);
      return boardMat((g, w, h) => {
        frameBoard(g, w, h, '#0e6b3a');
        list.forEach((q, i) => {
          const y = h * (0.27 + i * 0.47);
          g.textAlign = 'left';
          g.font = '800 72px Mukta, "Noto Sans Devanagari", sans-serif'; g.fillText(q.p.ne, 56, y - 12);
          g.font = '600 42px Oswald, Mukta, sans-serif'; g.fillText(q.p.en, 58, y + 54);
          g.textAlign = 'right';
          g.font = '700 66px Oswald, Mukta, sans-serif'; g.fillText(km(q.d), w - 56, y + 18);
          if (i === 0) g.fillRect(36, h * 0.5 + 2, w - 72, 5);
        });
      }, 768, 384);
    }
    const boards = [];           // { s, sg, w, h, mat }  sg: road side; traffic going +s keeps to +N (left)
    places.forEach((p, i) => {
      boards.push({ s: p.s - 70, sg: 1, w: 4.8, h: 2.0, mat: nameMats[i] });
      boards.push({ s: p.s + 70, sg: -1, w: 4.8, h: 2.0, mat: nameMats[i] });
      boards.push({ s: p.s + 260, sg: 1, w: 5.0, h: 2.5 });
      boards.push({ s: p.s - 260, sg: -1, w: 5.0, h: 2.5 });
    });
    for (const b of boards) {
      b.s = ((b.s % LOOP) + LOOP) % LOOP;
      for (let i = 0; i < 30 && (isGap(b.sg, kAt(b.s)) || isGap(b.sg, kAt(b.s) + 1)); i++) b.s = ((b.s - b.sg * r.step) % LOOP + LOOP) % LOOP;
    }
    KTM.places = places;

    // --- terrain (DEM, flattened inside the ring and by the road) with the satellite image -
    {
      const t = D.terrain, raw = Uint8Array.from(atob(t.h), c => c.charCodeAt(0));
      const hgt = new Int16Array(raw.buffer);
      const sb = D.sat.bounds, pos = [], uv = [], idx = [];
      for (let j = 0; j < t.ny; j++) for (let i = 0; i < t.nx; i++) {
        const x = t.x0 + i * t.step, y = t.y0 + j * t.step;
        pos.push(x, hgt[j * t.nx + i] / 10, -y);
        uv.push((x - sb[0]) / (sb[2] - sb[0]), (y - sb[1]) / (sb[3] - sb[1]));
      }
      for (let j = 0; j < t.ny - 1; j++) for (let i = 0; i < t.nx - 1; i++) {
        const a = j * t.nx + i, b = a + 1, c = a + t.nx, d = c + 1;
        idx.push(a, b, c, b, d, c);
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
      g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
      g.setIndex(idx); g.computeVertexNormals();
      const satTex = new THREE.TextureLoader().load(D.sat.file); satTex.colorSpace = THREE.SRGBColorSpace; satTex.anisotropy = MAX_ANISO;
      const terr = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ map: satTex, roughness: 1 }));
      terr.receiveShadow = true;
      scene.add(terr);
    }

    // --- chunks ---------------------------------------------------------------------
    const CH = 50;                                   // centreline points per chunk (200 m)
    const NCH = Math.ceil(n / CH);
    const nearBy = Array.from({ length: NCH }, () => []), farBy = Array.from({ length: NCH }, () => []);
    D.near.forEach(b => nearBy[Math.floor(b.k / CH)].push(b));
    D.far.forEach(f => farBy[Math.floor(f[7] / CH)].push(f));
    const chunks = new Map();
    let rand = () => 0;
    function seed(v) { let h = v * 7919 + 1; rand = () => (h = (h * 16807) % 2147483647) / 2147483647; }

    function buildChunk(ci) {
      const group = new THREE.Group(), bodies = [], lights = [], mats = [];
      ktmOwner = bodies;
      seed(ci + 1);
      const k0 = ci * CH, k1 = Math.min(n, k0 + CH);         // segments k0..k1-1 (the last one wraps to point 0)
      const sStart = S[k0], sEnd = sOf(k1);
      const gAsph = new Geo(), gMed = new Geo(), gKerb = new Geo(), gYel = new Geo(), gWhite = new Geo(), gPav = new Geo(), gVerge = new Geo(), gRail = new Geo();
      // strip between offsets f0(k) and f1(k) (functions), heights h0/h1; skip(k) leaves a segment out
      const hv = (h, k) => typeof h === 'function' ? h(k) : h;       // heights: numbers or functions of k
      function strip(g, sg, f0, f1, h0, h1, us, vs, skip) {
        for (let k = k0; k < k1; k++) {
          if (skip && skip(k)) continue;
          let a0 = sg * f0(k), a1 = sg * f1(k), b0 = sg * f0(k + 1), b1 = sg * f1(k + 1);
          let A0 = hv(h0, k), B0 = hv(h0, k + 1), A1 = hv(h1, k), B1 = hv(h1, k + 1);
          if (sg < 0) [a0, a1, b0, b1, A0, A1, B0, B1] = [a1, a0, b1, b0, A1, A0, B1, B0];
          const s0 = sOf(k), s1 = sOf(k + 1);
          g.quad(at(k, a0, A0), at(k + 1, b0, B0), at(k + 1, b1, B1), at(k, a1, A1),
            [s0 / us, a0 / vs + A0], [s1 / us, b0 / vs + B0], [s1 / us, b1 / vs + B1], [s0 / us, a1 / vs + A1]);
        }
      }
      const narrow = k => W[wrap(k)] === 0 && W[wrap(k + 1)] === 0;
      const c = v => () => v;
      const hk = k => flyH(sOf(k));
      const elev = k => hk(k) > 0 || hk(k + 1) > 0;          // the inner carriageways are up on the flyover
      for (const sg of [1, -1]) {
        const gp = k => isGap(sg, k) || isGap(sg, k + 1);
        // inner carriageway, separator, outer carriageway
        strip(gAsph, sg, c(M0), c(I1), 0, 0, 8, 8, elev);
        strip(gAsph, sg, S1, EDGE, 0, 0, 8, 8, narrow);
        strip(gMed, sg, c(I1), S1, 0.25, 0.25, 2, 2, narrow);
        for (const [lo, hi, skip] of [[c(M0), c(I1), elev], [S1, EDGE, narrow]]) {
          for (const e of [k => lo(k) + 0.3, k => hi(k) - 0.3]) strip(gYel, sg, k => e(k) - 0.06, k => e(k) + 0.06, 0.008, 0.008, 1, 1, skip);
        }
        // kerb faces
        strip(gKerb, sg, c(M0), c(M0), 0, 0.25, 2, 1, elev);
        strip(gKerb, sg, c(I1), c(I1), 0, 0.25, 2, 1, narrow);
        strip(gKerb, sg, S1, S1, 0, 0.25, 2, 1, narrow);
        strip(gKerb, sg, EDGE, EDGE, 0, 0.2, 2, 1, gp);
        // footpath and verge; at side roads the asphalt runs on to meet them
        strip(gPav, sg, EDGE, k => EDGE(k) + FOOT, 0.2, 0.2, 1.3, 1.3, gp);
        strip(gVerge, sg, k => EDGE(k) + FOOT, k => EDGE(k) + FOOT + 4, 0.2, -0.05, 3, 3, gp);
        strip(gAsph, sg, EDGE, k => EDGE(k) + FOOT + 4, 0, 0, 8, 8, k => !gp(k));
        // bridge parapets
        strip(gRail, sg, k => EDGE(k) + FOOT, k => EDGE(k) + FOOT, 0.2, 1.3, 2, 1, k => !inBridge(sOf(k)));
        // lane dashes 3 m on, 6 m off, at the middle of each carriageway
        for (const [mid, need] of [[() => M0 + r.shoulder / 2 + r.lane, () => true], [k => S1(k) + r.shoulder / 2 + r.lane, k => W[wrap(k)] > 0.99]]) {
          for (let s = Math.ceil(sStart / 9) * 9; s < sEnd - 1; s += 9) {
            const A = frame(s), B = frame(s + 3);
            if (!need(A.k) || !need(B.k)) continue;
            const pa = (F, o) => P2(F.x - F.ty * o, F.y + F.tx * o, 0.01 + (mid(F.k) < I1 ? flyH(sOf(F.k) + F.f * r.step) : 0));
            const oa = sg * mid(A.k), ob = sg * mid(B.k), d = 0.07;
            gWhite.quad(pa(A, oa - d), pa(B, ob - d), pa(B, ob + d), pa(A, oa + d), [0, 0], [1, 0], [1, 1], [0, 1]);
          }
        }
      }
      strip(gMed, 1, c(-M0), c(M0), 0.25, 0.25, 2, 2, elev);
      // the flyover: deck, lane markings, parapets, central barrier, fascia / ramp walls, piers
      const gConc = new Geo(), gPier = new Geo();
      {
        const DW = I1 + 0.3, noE = k => !elev(k), deep = k => hk(k) > 4.5 && hk(k + 1) > 4.5;
        const up = d => k => hk(k) + d;
        strip(gMed, 1, c(-I1), c(I1), 0.02, 0.02, 2, 2, noE);                       // ground under the deck
        for (const sg of [1, -1]) {
          strip(gAsph, sg, c(0.3), c(DW), hk, hk, 8, 8, noE);
          for (const e of [M0 + 0.3, I1 - 0.3]) strip(gYel, sg, c(e - 0.06), c(e + 0.06), up(0.008), up(0.008), 1, 1, noE);
          strip(gConc, sg, c(DW), c(DW), k => deep(k) ? hk(k) - 1.2 : 0, hk, 3, 3, noE);  // fascia, solid wall on the ramps
          strip(gConc, sg, c(DW), c(DW), hk, up(1.0), 3, 3, noE);                     // parapet
          strip(gConc, sg, c(DW - 0.25), c(DW - 0.25), hk, up(1.0), 3, 3, noE);
          strip(gConc, sg, c(DW - 0.25), c(DW), up(1.0), up(1.0), 3, 3, noE);
          strip(gConc, sg, c(0.3), c(0.3), hk, up(0.85), 3, 3, noE);                  // central barrier
        }
        strip(gConc, 1, c(-0.3), c(0.3), up(0.85), up(0.85), 3, 3, noE);
        strip(gConc, 1, c(DW), c(-DW), k => hk(k) - 1.2, k => hk(k) - 1.2, 4, 4, k => !deep(k));   // underside (faces down)
        for (let k = k0; k < k1; k++) {                                              // where the solid ramp becomes a bridge
          if (deep(k) === deep(k - 1) || !elev(k)) continue;
          const h = hk(k) - 1.2;
          gConc.quad(at(k, -DW, 0), at(k, DW, 0), at(k, DW, h), at(k, -DW, h), [0, 0], [1, 0], [1, 1], [0, 1]);
        }
        for (const [a, b] of r.flyovers || []) {                                    // piers every 30 m
          for (let ps = a + 15; ps < b; ps += 30) {
            if (ps < sStart || ps >= sEnd) continue;
            const F = frame(ps), h = flyH(ps) - 1.2, tz = [F.tx, -F.ty], nz = [-F.ty, -F.tx];
            gPier.box(F.x, h / 2, -F.y, tz, nz, 0.7, h / 2, 1.6);
            gPier.box(F.x, h - 0.35, -F.y, tz, nz, 0.9, 0.35, DW - 1.0);              // pier cap
            poolBox([0.7, h / 2, 1.6], [F.x, h / 2, -F.y], Math.atan2(F.ty, F.tx));
          }
        }
      }
      gConc.mesh(concrete, group, false); gPier.mesh(concrete, group, true);
      gAsph.mesh(asphalt, group, false); gMed.mesh(medianMat, group, false); gKerb.mesh(kerb, group, false);
      gYel.mesh(yellow, group, false); gWhite.mesh(whiteP, group, false); gPav.mesh(pavers, group, false);
      gVerge.mesh(vergeMat, group, false); gRail.mesh(rail, group, false);

      // side roads that join in this chunk
      {
        const g = new Geo();
        for (const st of D.stubs) {
          if (st.k < k0 || st.k >= k1) continue;
          const p = [];
          for (let k = 0; k < st.p.length; k += 2) p.push([st.p[k], st.p[k + 1]]);
          let run = 0;
          for (let j = 0; j + 1 < p.length; j++) {
            const a = p[j], b = p[j + 1], L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
            const nx = -(b[1] - a[1]) / L * st.w / 2, ny = (b[0] - a[0]) / L * st.w / 2, h = 0.012;
            // (a - n) -> (b - n) -> (b + n) -> (a + n) runs counter-clockwise seen from above: faces up
            g.quad(P2(a[0] - nx, a[1] - ny, h), P2(b[0] - nx, b[1] - ny, h), P2(b[0] + nx, b[1] + ny, h), P2(a[0] + nx, a[1] + ny, h),
              [run / 8, 0], [(run + L) / 8, 0], [(run + L) / 8, st.w / 8], [run / 8, st.w / 8]);
            run += L;
          }
        }
        g.mesh(asphalt, group, false);
      }

      // road colliders: median, separators, footpaths, bridge parapets (8 m boxes)
      for (let k = k0; k < k1; k += 2) {
        const a = pts[wrap(k)], b = pts[wrap(k + 2)];
        const cx = (a[0] + b[0]) / 2, cy = (a[1] + b[1]) / 2, L = Math.hypot(b[0] - a[0], b[1] - a[1]);
        const tx = (b[0] - a[0]) / L, ty = (b[1] - a[1]) / L, nx = -ty, ny = tx, len = L / 2 + 0.3;
        const yaw = Math.atan2(ty, tx), km = wrap(k + 1);
        const add = (o, hw, h) => poolBox([len, h / 2, hw], [cx + nx * o, h / 2, -(cy + ny * o)], yaw);
        add(0, M0, 0.25);
        const ha = flyH(sOf(k)), hb = flyH(sOf(k) + L);
        if (ha > 0 || hb > 0) {                         // flyover deck (solid on the ramps), parapets, barrier
          const hm = (ha + hb) / 2, pitch = Math.atan2(hb - ha, L), th = hm < 4.5 ? Math.max(0.4, hm) : 0.4, DW = I1 + 0.3;
          poolBoxP([len, th / 2, DW], [cx, hm - th / 2, -cy], yaw, pitch);
          for (const o of [DW - 0.12, -(DW - 0.12)]) poolBoxP([len, 0.5, 0.15], [cx + nx * o, hm + 0.5, -(cy + ny * o)], yaw, pitch);
          poolBoxP([len, 0.42, 0.3], [cx, hm + 0.42, -cy], yaw, pitch);
        }
        for (const sg of [1, -1]) {
          if (W[km] > 0.3) add(sg * (I1 + S1(km)) / 2, r.sep * W[km] / 2, 0.25);
          if (!isGap(sg, k) && !isGap(sg, k + 1) && !isGap(sg, k + 2)) add(sg * (EDGE(km) + FOOT / 2), FOOT / 2, 0.2);
          if (inBridge(sOf(k))) add(sg * (EDGE(km) + FOOT), 0.15, 1.3);
        }
      }

      // near buildings: windows, shops, signboards, balconies, water tanks
      const wallsG = new Geo(), shopG = new Geo(), roofG = new Geo(), extraG = new Geo();
      const signG = signMats.map(() => new Geo());
      const tanks = [];
      for (const b of nearBy[ci]) {
        const ring = [];
        for (let k = 0; k < b.p.length; k += 2) ring.push([b.p[k], b.p[k + 1]]);
        const H = b.f * 2.9 + 0.5;
        const col = WALL_COLS[b.c % WALL_COLS.length].clone().multiplyScalar(0.85 + (b.c % 31) / 100);
        let per = 0;
        const dist = Math.hypot(b.b[0] - pts[b.k][0], b.b[1] - pts[b.k][1]);
        for (let j = 0; j < ring.length; j++) {
          const a = ring[j], c2 = ring[(j + 1) % ring.length];
          const L = Math.hypot(c2[0] - a[0], c2[1] - a[1]);
          if (L < 0.05) continue;
          const ox = (c2[1] - a[1]) / L, oy = -(c2[0] - a[0]) / L;       // outward (CCW ring)
          const mx = (a[0] + c2[0]) / 2, my = (a[1] + c2[1]) / 2;
          const kk = locate(mx, my).k;
          const tx = pts[kk][0] - mx, ty = pts[kk][1] - my, tl = Math.hypot(tx, ty) || 1;
          const facing = (ox * tx + oy * ty) / tl > 0.6;
          const shop = facing && dist < 45 && L > 2.5;
          const u0 = per / 3.1, u1 = (per + L) / 3.1;
          const A = (h) => P2(a[0], a[1], h), C = (h) => P2(c2[0], c2[1], h);
          (shop ? shopG : wallsG).quad(A(-0.5), C(-0.5), C(2.9), A(2.9), [u0 * 1.5, 0], [u1 * 1.5, 0], [u1 * 1.5, 1], [u0 * 1.5, 1], shop ? null : col);
          wallsG.quad(A(2.9), C(2.9), C(H), A(H), [u0, 1], [u1, 1], [u1, H / 2.9], [u0, H / 2.9], col);
          per += L;
          const ax = [(c2[0] - a[0]) / L, -(c2[1] - a[1]) / L], az = [ox, -oy];       // three.js x/z of along and outward
          if (shop && rand() < 0.85) {
            const w = Math.min(L - 0.4, 6), si = Math.floor(rand() * signMats.length);
            const cx = mx + ox * 0.14, cy = my + oy * 0.14;
            extraG.box(cx, 3.25, -cy, ax, az, w / 2, 0.38, 0.06, new THREE.Color(0x222222));
            const p0 = P2(cx + ox * 0.07 - (c2[0] - a[0]) / L * w / 2, cy + oy * 0.07 - (c2[1] - a[1]) / L * w / 2, 2.9);
            const p1 = P2(cx + ox * 0.07 + (c2[0] - a[0]) / L * w / 2, cy + oy * 0.07 + (c2[1] - a[1]) / L * w / 2, 2.9);
            const up = new THREE.Vector3(0, 0.72, 0);
            signG[si].quad(p0, p1, p1.clone().add(up), p0.clone().add(up), [0, 0], [1, 0], [1, 1], [0, 1]);
          }
          if (facing && dist < 60 && L > 3 && b.f >= 2) {
            const bal = col.clone().multiplyScalar(1.1);
            for (let f = 1; f < b.f; f++) {
              if (rand() < 0.25) continue;
              const cx = mx + ox * 0.5, cy = my + oy * 0.5;
              extraG.box(cx, f * 2.9, -cy, ax, az, L / 2 - 0.3, 0.07, 0.5, bal);
              extraG.box(cx + ox * 0.45, f * 2.9 + 0.5, -(cy + oy * 0.45), ax, az, L / 2 - 0.3, 0.45, 0.05, bal);
            }
          }
        }
        // roof
        const shape = ring.map(p => new THREE.Vector2(p[0], p[1]));
        const tris = THREE.ShapeUtils.triangulateShape(shape, []);
        const base = roofG.p.length / 3;
        for (const p of ring) { roofG.p.push(p[0], H, -p[1]); roofG.uv.push(0, 0); }
        for (const t of tris) roofG.i.push(base + t[0], base + t[2], base + t[1]);
        if (b.b[2] * b.b[3] > 20 && rand() < 0.7) tanks.push([b.b[0], b.b[1], H]);
        poolBox([b.b[2] / 2, H / 2, b.b[3] / 2], [b.b[0], H / 2, -b.b[1]], b.b[4]);
      }
      wallsG.mesh(walls, group); shopG.mesh(shutters, group); roofG.mesh(roofMat, group, false);
      extraG.mesh(colMat, group, false);
      signG.forEach((g, i) => g.mesh(signMats[i], group, false));
      if (tanks.length) {
        const tm = new THREE.InstancedMesh(tankGeo, tankMat, tanks.length);
        const m4 = new THREE.Matrix4();
        tanks.forEach((t, i) => { m4.makeTranslation(t[0], t[2] + 0.62, -t[1]); tm.setMatrixAt(i, m4); });
        tm.castShadow = true; group.add(tm);
      }
      // far buildings (boxes on the terrain)
      if (farBy[ci].length) {
        const fm = new THREE.InstancedMesh(farGeo, farMat, farBy[ci].length);
        const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s3 = new THREE.Vector3(), p = new THREE.Vector3(), Y = new THREE.Vector3(0, 1, 0);
        farBy[ci].forEach((f, i) => {
          const [cx, cy, w, d, a, fl, cidx, , hb] = f;
          m4.compose(p.set(cx, hb - 0.3, -cy), q.setFromAxisAngle(Y, a), s3.set(w, fl * 2.9 + 0.5, d));
          fm.setMatrixAt(i, m4);
          fm.setColorAt(i, WALL_COLS[cidx % WALL_COLS.length]);
        });
        fm.receiveShadow = true; group.add(fm);
      }

      // poles with wires, median street lights, roadside trees
      const poleG = new Geo(), lightG = new Geo(), wire = [];
      const grey = new THREE.Color(0x77756f), dark = new THREE.Color(0x333333), lamp = new THREE.Color(0xdddddd);
      for (const sg of [1, -1]) {
        const first = sg > 0 ? 10 : 27;
        const poleAt = s => {
          const F = frame(s);
          if (isGap(sg, F.k) || isGap(sg, F.k + 1)) return null;
          const o = sg * (EDGE(F.k) + FOOT - 0.4);
          return { x: F.x - F.ty * o, y: F.y + F.tx * o, tx: F.tx, ty: F.ty };
        };
        const tops = q => [-0.8, -0.3, 0.3, 0.8].map(d => new THREE.Vector3(q.x + q.tx * d, 8.65, -(q.y + q.ty * d)));
        let s = first + Math.ceil((sStart - first) / 36) * 36;
        let last = s - 36 >= first ? poleAt(s - 36) : null;
        for (; s < sEnd && s < LOOP - 20; s += 36) {
          const q = poleAt(s);
          if (q) {
            const tz = [q.tx, -q.ty], nz = [-q.ty * sg, -q.tx * sg];
            poleG.box(q.x, 4.6, -q.y, tz, nz, 0.12, 4.6, 0.12, grey);
            poleG.box(q.x, 8.6, -q.y, tz, nz, 0.9, 0.05, 0.06, dark);
            poolBox([0.15, 4.6, 0.15], [q.x, 4.6, -q.y]);
            if (last) {
              const A = tops(last), B = tops(q);
              for (let w = 0; w < 4; w++) for (const drop of [0, 0.25]) {
                let prev = null;
                for (let f = 0; f <= 1.0001; f += 0.125) {
                  const v = A[w].clone().lerp(B[w], f); v.y -= (0.9 + drop) * 4 * f * (1 - f) + drop;
                  if (prev) wire.push(prev, v);
                  prev = v;
                }
              }
            }
          }
          last = q;
        }
      }
      for (let s = 20 + Math.ceil((sStart - 20) / 32) * 32; s < sEnd && s < LOOP - 12; s += 32) {
        const F = frame(s), x = F.x, y = F.y, tz = [F.tx, -F.ty], fh = flyH(s);
        lightG.box(x, 5.25 + fh, -y, tz, [-tz[1], tz[0]], 0.09, 5.0, 0.09, grey);
        for (const sg of [1, -1]) {
          const nx = -F.ty * sg, ny = F.tx * sg, nz = [nx, -ny];
          lightG.box(x + nx * 1.0, 10.15 + fh, -(y + ny * 1.0), nz, tz, 1.0, 0.04, 0.04, grey);
          lightG.box(x + nx * 1.9, 10.07 + fh, -(y + ny * 1.9), nz, tz, 0.35, 0.06, 0.14, lamp);
          lights.push(new THREE.Vector3(x + nx * 1.9, 10.0 + fh, -(y + ny * 1.9)));
        }
      }
      poleG.mesh(colMat, group, false); lightG.mesh(colMat, group, false);
      if (wire.length) group.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(wire), wireMat));
      {
        const spots = [];
        for (const sg of [1, -1]) for (let s = Math.ceil(sStart / 7) * 7 + 5; s < sEnd; s += 7) {
          if (rand() > 0.35) continue;
          const F = frame(s);
          if (isGap(sg, F.k) || isGap(sg, F.k + 1) || inBridge(s)) continue;
          const o = sg * (EDGE(F.k) + FOOT + 1 + rand() * 2);
          spots.push([F.x - F.ty * o, F.y + F.tx * o, 0.6 + rand() * 0.6]);
        }
        if (spots.length) {
          const tr = new THREE.InstancedMesh(trunkGeo, trunkMat, spots.length);
          const cr = new THREE.InstancedMesh(broad.geometry, crownMat, spots.length);
          const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s3 = new THREE.Vector3(), p = new THREE.Vector3();
          const cc = new THREE.Color(), Y = new THREE.Vector3(0, 1, 0);
          spots.forEach(([x, y, k], i) => {
            m4.compose(p.set(x, 0, -y), q.identity(), s3.set(k, k, k)); tr.setMatrixAt(i, m4);
            m4.compose(p.set(x, 2.1 * k, -y), q.setFromAxisAngle(Y, rand() * 6.3), s3.set(k, k, k)); cr.setMatrixAt(i, m4);
            cr.setColorAt(i, cc.setHSL(0.24 + rand() * 0.08, 0.45, 0.18 + rand() * 0.1));
            poolCyl(0.28 * k, 2.4 * k, [x, 1.2 * k, -y]);
          });
          tr.castShadow = cr.castShadow = true;
          group.add(tr, cr);
        }
      }

      // place boards standing on the footpath, facing the traffic on that side
      {
        const postG = new Geo();
        for (const b of boards) {
          if (b.s < sStart || b.s >= sEnd) continue;
          const F = frame(b.s), o = b.sg * (EDGE(F.k) + FOOT * 0.55);
          const x = F.x - F.ty * o, y = F.y + F.tx * o;
          const fx = -F.tx * b.sg, fy = -F.ty * b.sg;           // toward the traffic coming on that side
          const ax = [-fy, fx];                                 // board's left-to-right as seen by that traffic
          const bottom = 2.3, top = bottom + b.h;
          for (const e of [-1, 1]) {
            const px = x + ax[0] * e * (b.w / 2 - 0.25), py = y + ax[1] * e * (b.w / 2 - 0.25);
            postG.box(px, top / 2, -py, [ax[0], -ax[1]], [fx, -fy], 0.06, top / 2, 0.06, grey);
            poolCyl(0.08, top, [px, top / 2, -py]);
          }
          postG.box(x - fx * 0.05, (bottom + top) / 2, -(y - fy * 0.05), [ax[0], -ax[1]], [fx, -fy], b.w / 2 + 0.04, b.h / 2 + 0.04, 0.03, dark);
          let mat = b.mat;
          if (!mat) { mat = dirMat(b.s, b.sg); mats.push(mat); }
          const g = new Geo();
          const p0 = P2(x - ax[0] * b.w / 2 + fx * 0.01, y - ax[1] * b.w / 2 + fy * 0.01, bottom);
          const p1 = P2(x + ax[0] * b.w / 2 + fx * 0.01, y + ax[1] * b.w / 2 + fy * 0.01, bottom);
          const up = new THREE.Vector3(0, b.h, 0);
          g.quad(p0, p1, p1.clone().add(up), p0.clone().add(up), [0, 0], [1, 0], [1, 1], [0, 1]);
          g.mesh(mat, group, false);
        }
        postG.mesh(colMat, group, false);
      }

      ktmOwner = null;
      scene.add(group);
      return { group, bodies, lights, mats };
    }
    function dropChunk(ci) {
      const ch = chunks.get(ci);
      scene.remove(ch.group);
      ch.group.traverse(o => {
        if (o.isInstancedMesh) o.dispose();
        if ((o.isMesh || o.isLineSegments) && !shared.has(o.geometry)) o.geometry.dispose();
      });
      for (const m of ch.mats) { if (m.userData.redraw) redraw.delete(m.userData.redraw); m.map.dispose(); m.dispose(); }
      for (const b of ch.bodies) poolDrop(b);
      chunks.delete(ci);
    }
    const RANGE = 4;                                    // chunks each way that stay built (800 m)
    const cdist = (a, b) => { const d = Math.abs(a - b); return Math.min(d, NCH - d); };
    function chunkStream(x, z, all = false) {
      const ci = Math.floor(locate(x, -z).k / CH);
      let changed = false;
      for (const c of [...chunks.keys()]) if (cdist(c, ci) > RANGE + 1) { dropChunk(c); changed = true; }
      // nearest first; one new chunk per frame while driving keeps frames smooth
      for (let d = 0; d <= RANGE; d++) {
        for (const c of d ? [ci + d, ci - d] : [ci]) {
          const cc = ((c % NCH) + NCH) % NCH;
          if (chunks.has(cc)) continue;
          chunks.set(cc, buildChunk(cc)); changed = true;
          if (!all) { d = RANGE + 1; break; }
        }
      }
      if (changed) {
        KTM.lights = [...chunks.values()].flatMap(c => c.lights);
        ktmLastCell = null;
      }
    }
    KTM.stream = (x, z) => {
      chunkStream(x, z); poolStream(x, z);
      // the physics ground is an 8 km box: keep it centred under the bus (the loop is 9 km across)
      const g = world.ground, gx = Math.round(x / 500) * 500, gz = Math.round(z / 500) * 500;
      if (g && (g.position.x !== gx || g.position.z !== gz)) { g.position.x = gx; g.position.z = gz; g.aabbNeedsUpdate = true; }
    };

    // --- traffic ------------------------------------------------------------------------
    // Low-poly Kathmandu traffic: motorbikes, small cars, SUVs, Hiace microbuses,
    // buses, trucks and Safa tempos. Each drives on the left in a lane, follows the
    // vehicle ahead (intelligent driver model, the player's bus included), changes
    // lane when held up and merges where the road narrows from 8 to 4 lanes.
    const TYPES = [
      { name: 'bike', n: 46, L: 2.0, Wd: 0.8, Hh: 1.6, v0: [11, 17], a: 2.6, cols: ['#c81d25', '#1d1d1f', '#1f4fa8', '#e8e8e8', '#2f7d32', '#f2b705'] },
      { name: 'car', n: 34, L: 3.9, Wd: 1.7, Hh: 1.5, v0: [10, 15], a: 2.0, cols: ['#f1f1ef', '#c7c9cc', '#9b1b1f', '#1e3f7a', '#202124', '#e0e0d8', '#7b8088'] },
      { name: 'suv', n: 10, L: 4.6, Wd: 1.85, Hh: 1.8, v0: [10, 15], a: 1.8, cols: ['#f4f4f2', '#2a2b2e', '#5d6168', '#7a1c1c'] },
      { name: 'micro', n: 14, L: 5.3, Wd: 1.9, Hh: 2.25, v0: [9, 14], a: 1.5, cols: ['#f3f3f0', '#2563a8', '#e8e6df'] },
      { name: 'bus', n: 7, L: 10.5, Wd: 2.5, Hh: 3.15, v0: [8, 12], a: 1.0, cols: ['#2f8f46', '#c0392b', '#1f5fa8', '#e2a312', '#f2f2f0'] },
      { name: 'truck', n: 6, L: 8.0, Wd: 2.45, Hh: 3.1, v0: [7, 11], a: 0.8, cols: ['#e06a10', '#c0262d', '#1f62b0', '#e5b30e'] },
      { name: 'tempo', n: 7, L: 3.3, Wd: 1.35, Hh: 1.85, v0: [7, 10], a: 1.2, cols: ['#2e8b57', '#2a6fb5', '#f0f0ee'] },
    ];
    const WHITE = new THREE.Color(1, 1, 1), GLASS = new THREE.Color(0x1a2128), TYRE = new THREE.Color(0x151515), METAL = new THREE.Color(0x9a9c9f),
      JACKET = new THREE.Color(0x2a2c33), WOOD = new THREE.Color(0x8b5a2b), BLACK = new THREE.Color(0x222222);
    const X = [1, 0], Z = [0, 1];
    // body (tinted per vehicle), details (fixed colours), head lamps, tail lamps; local +x = forward
    function makeType(t) {
      const body = new Geo(), det = new Geo(), head = new Geo(), tail = new Geo();
      const L = t.L, w = t.Wd / 2;
      const wheels = (xs, r, wz) => { for (const x of xs) for (const z of [-wz, wz]) det.wheel(x, r, z, r, 0.22, TYRE); };
      const pair = (g, x, y, z, hx, hy, hz) => { g.box(x, y, z, X, Z, hx, hy, hz, WHITE); g.box(x, y, -z, X, Z, hx, hy, hz, WHITE); };
      if (t.name === 'bike') {
        det.wheel(0.68, 0.3, 0, 0.3, 0.1, TYRE); det.wheel(-0.62, 0.3, 0, 0.3, 0.12, TYRE);
        body.box(0.05, 0.62, 0, X, Z, 0.55, 0.16, 0.16, WHITE);            // tank and side panels
        det.box(-0.35, 0.82, 0, X, Z, 0.4, 0.06, 0.15, JACKET);            // seat
        det.box(0.6, 0.85, 0, X, Z, 0.05, 0.3, 0.04, METAL);               // forks
        det.box(0.62, 1.12, 0, X, Z, 0.03, 0.03, 0.34, METAL);             // handlebar
        det.box(-0.2, 1.2, 0, X, Z, 0.17, 0.33, 0.2, JACKET);              // rider
        det.box(0.1, 1.08, 0, X, Z, 0.28, 0.05, 0.22, JACKET);             // arms
        det.box(-0.3, 0.75, 0, X, Z, 0.3, 0.09, 0.2, new THREE.Color(0x30343d));     // legs
        body.box(-0.18, 1.67, 0, X, Z, 0.15, 0.14, 0.13, WHITE);           // helmet
        head.box(0.74, 0.98, 0, X, Z, 0.03, 0.06, 0.07, WHITE);
        tail.box(-0.82, 0.8, 0, X, Z, 0.02, 0.04, 0.08, WHITE);
      } else if (t.name === 'car' || t.name === 'suv') {
        const suv = t.name === 'suv', r = suv ? 0.36 : 0.3, top = t.Hh, cab = L * (suv ? 0.36 : 0.28);
        const ch = (top - r - 0.84) / 2;
        body.box(0, r + 0.42, 0, X, Z, L / 2, 0.42, w, WHITE);
        body.box(-L * 0.08, r + 0.84 + ch, 0, X, Z, cab, ch, w - 0.08, WHITE);
        det.box(-L * 0.08, r + 0.84 + ch + 0.02, 0, X, Z, cab + 0.02, ch - 0.08, w - 0.06, GLASS);
        det.box(0, r + 0.08, 0, X, Z, L / 2 + 0.03, 0.08, w + 0.01, BLACK);          // bumpers and sills
        wheels([L * 0.32, -L * 0.32], r, w - 0.1);
        pair(head, L / 2 + 0.01, r + 0.55, w - 0.3, 0.02, 0.07, 0.17);
        pair(tail, -L / 2 - 0.01, r + 0.6, w - 0.2, 0.02, 0.08, 0.12);
      } else if (t.name === 'micro') {
        body.box(0, 1.25, 0, X, Z, L / 2, 0.92, w, WHITE);
        det.box(0.1, 1.6, 0, X, Z, L / 2 - 0.05, 0.32, w + 0.01, GLASS);
        det.box(0, 0.98, 0, X, Z, L / 2 + 0.005, 0.09, w + 0.012, new THREE.Color(0xb3202a));       // stripe
        det.box(0, 0.38, 0, X, Z, L / 2 + 0.03, 0.08, w + 0.01, BLACK);
        wheels([L * 0.34, -L * 0.3], 0.34, w - 0.12);
        pair(head, L / 2 + 0.01, 0.75, w - 0.3, 0.02, 0.08, 0.16);
        pair(tail, -L / 2 - 0.01, 0.85, w - 0.12, 0.02, 0.14, 0.08);
      } else if (t.name === 'bus') {
        body.box(0, 1.85, 0, X, Z, L / 2, 1.3, w, WHITE);
        det.box(0.2, 2.3, 0, X, Z, L / 2 - 0.3, 0.5, w + 0.01, GLASS);
        det.box(L / 2 - 0.02, 2.15, 0, X, Z, 0.03, 0.75, w - 0.12, GLASS);
        det.box(0, 1.3, 0, X, Z, L / 2 + 0.005, 0.12, w + 0.012, new THREE.Color(0xf2f2ee));
        det.box(0, 3.25, -0.2, X, Z, L * 0.35, 0.1, w - 0.3, new THREE.Color(0x3a3a3a));          // roof rack
        det.box(0, 0.55, 0, X, Z, L / 2 + 0.03, 0.1, w + 0.01, BLACK);
        wheels([L * 0.3, -L * 0.25], 0.5, w - 0.2);
        pair(head, L / 2 + 0.01, 0.95, w - 0.35, 0.02, 0.1, 0.2);
        pair(tail, -L / 2 - 0.01, 1.0, w - 0.2, 0.02, 0.2, 0.1);
      } else if (t.name === 'truck') {
        body.box(L / 2 - 1.0, 1.75, 0, X, Z, 1.0, 1.2, w, WHITE);                                 // cab
        det.box(L / 2 - 0.02, 2.2, 0, X, Z, 0.03, 0.45, w - 0.15, GLASS);
        det.box(-0.95, 1.85, 0, X, Z, L / 2 - 1.05, 1.15, w + 0.02, WOOD);                          // high wooden cargo body
        det.box(-0.95, 0.72, 0, X, Z, L / 2 - 1.05, 0.08, w - 0.2, BLACK);
        det.box(L / 2 - 1.0, 3.05, 0, X, Z, 1.0, 0.12, w, new THREE.Color(0xf2c230));             // decorated cab top
        wheels([L / 2 - 1.2, -L * 0.18, -L * 0.33], 0.5, w - 0.22);
        pair(head, L / 2 + 0.01, 0.95, w - 0.35, 0.02, 0.1, 0.18);
        pair(tail, -L / 2 + 0.08, 0.75, w - 0.2, 0.02, 0.08, 0.12);
      } else {                                                                                      // Safa tempo
        body.box(-0.2, 1.1, 0, X, Z, L / 2 - 0.2, 0.75, w, WHITE);
        body.box(L / 2 - 0.35, 0.95, 0, X, Z, 0.35, 0.6, w - 0.15, WHITE);
        det.box(L / 2 - 0.2, 1.4, 0, X, Z, 0.21, 0.25, w - 0.2, GLASS);
        det.box(-0.3, 1.45, 0, X, Z, L / 2 - 0.4, 0.25, w + 0.01, GLASS);
        det.box(-0.2, 1.9, 0, X, Z, L / 2 - 0.1, 0.05, w + 0.05, new THREE.Color(0xf0f0ee));
        det.wheel(L / 2 - 0.4, 0.26, 0, 0.26, 0.15, TYRE); wheels([-L * 0.3], 0.26, w - 0.1);
        head.box(L / 2 + 0.01, 0.95, 0, X, Z, 0.02, 0.08, 0.1, WHITE);
        pair(tail, -L / 2 + 0.19, 0.6, w - 0.15, 0.02, 0.06, 0.08);
      }
      const inst = (g, mat, shadow) => {
        const m = new THREE.InstancedMesh(g.geometry(), mat, t.n);
        m.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
        m.frustumCulled = false; m.castShadow = shadow; m.receiveShadow = shadow;
        scene.add(m);
        return m;
      };
      t.mBody = inst(body, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.35, metalness: 0.3, side: THREE.DoubleSide }), true);
      t.mDet = inst(det, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.6, side: THREE.DoubleSide }), true);
      t.mHead = inst(head, new THREE.MeshBasicMaterial({ toneMapped: false }), false);
      t.mTail = inst(tail, new THREE.MeshBasicMaterial({ toneMapped: false }), false);
      const cc = new THREE.Color();
      for (let i = 0; i < t.n; i++) {
        t.mBody.setColorAt(i, cc.set(t.cols[i % t.cols.length]));
        t.mHead.setColorAt(i, cc.setRGB(1, 1, 1)); t.mTail.setColorAt(i, cc.setRGB(0.5, 0.02, 0.02));
      }
    }
    TYPES.forEach(makeType);

    // lane centres (distance from the centreline): 0,1 inner carriageway, 2,3 outer
    const laneOff = (lane, F) => lane < 2 ? M0 + r.shoulder / 2 + r.lane * (lane + 0.5)
      : I1 + r.sep * F.w + r.shoulder / 2 + r.lane * (lane - 1.5);
    const lanesAt = w => w > 0.999 ? 4 : 2;
    const slow = t => t.name === 'bus' || t.name === 'truck' || t.name === 'tempo';
    const cars = [];
    TYPES.forEach(t => { for (let i = 0; i < t.n; i++) cars.push({ t, i, s: 0, dir: 1, lane: 0, lat: 0, v: 0, v0: 10, wob: 0, stop: 0, body: null, brake: false, lc: 0, gap: 1e9, vl: 0, want: 0, end: 1e9 }); });
    KTM.cars = cars;
    const WIN = 520;                                   // traffic lives this far ahead of / behind the bus
    let busS = 0, busO = 0, busV = 0;
    let h2 = 12345;
    const rand2 = () => (h2 = (h2 * 16807) % 2147483647) / 2147483647;
    const rel = s => { let d = ((s - busS) % LOOP + LOOP) % LOOP; if (d > LOOP / 2) d -= LOOP; return d; };
    function place(c, sNew) {
      for (let tries = 0; tries < 12; tries++) {
        const dir = rand2() < 0.5 ? 1 : -1, s = ((sNew + (tries ? (rand2() - 0.5) * 120 : 0)) % LOOP + LOOP) % LOOP;
        const F = frame(s), nl = lanesAt(F.w);
        let lane = Math.floor(rand2() * nl);
        if (slow(c.t)) lane = nl === 4 ? 3 : 1;                 // slow traffic keeps left
        const wob = c.t.name === 'bike' ? (rand2() - 0.5) * 1.6 : 0;
        const lat = laneOff(lane, F) + wob, ds = rel(s);
        // clear of the bus and of the others in the lane
        if (Math.abs(ds) < 30) continue;
        if (cars.some(o => o !== c && o.dir === dir && Math.abs(o.lat - lat) < 2.2 && Math.abs(rel(o.s) - ds) < (o.t.L + c.t.L) / 2 + 6)) continue;
        Object.assign(c, { s, dir, lane, lat, want: lat, wob, stop: 0, brake: false, lc: 0, gap: 1e9, end: 1e9 });
        c.v0 = c.t.v0[0] + rand2() * (c.t.v0[1] - c.t.v0[0]);
        c.v = c.v0 * 0.8;
        return;
      }
      c.s = (busS + LOOP / 2) % LOOP;                  // parked out of sight until the next try
    }
    const q4 = new THREE.Quaternion(), p4 = new THREE.Vector3(), one = new THREE.Vector3(1, 1, 1), Yax = new THREE.Vector3(0, 1, 0), m4 = new THREE.Matrix4();
    const tailCol = new THREE.Color(), headCol = new THREE.Color(), cY = new CANNON.Vec3(0, 1, 0);
    const qP = new THREE.Quaternion(), Zax = new THREE.Vector3(0, 0, 1);
    KTM.update = (dt) => {
      if (!bus) return;
      dt = Math.min(dt, 0.1);
      const bp = bus.chassis.position, L0 = locate(bp.x, -bp.z);
      busS = L0.s; busO = L0.o;
      const F0 = frame(busS);
      busV = bus.chassis.velocity.x * F0.tx - bus.chassis.velocity.z * F0.ty;     // bus speed along +s
      // is the lane at lat free for c (the player's bus counts as traffic too)?
      const laneFree = (c, lat) => {
        const p = rel(c.s), bp = c.dir * (rel(busS) - p);
        if (Math.abs(c.dir * busO - lat) < 3 && bp < (c.t.L + 11) / 2 + 10 && -bp < (c.t.L + 11) / 2 + 8) return false;
        return cars.every(o => o === c || o.dir !== c.dir || Math.min(Math.abs(o.lat - lat), Math.abs(o.want - lat)) > (o.t.Wd + c.t.Wd) / 2 + 0.3 ||
          c.dir * (rel(o.s) - p) > (c.t.L + o.t.L) / 2 + 8 || c.dir * (p - rel(o.s)) > (c.t.L + o.t.L) / 2 + 6);
      };
      // lanes: leave the outer carriageway where it tapers away; pass slow traffic
      for (const c of cars) {
        const F = frame(c.s);
        c.lc -= dt; c.end = 1e9;
        if (c.lane >= 2) {
          let d = 0;
          while (d < 200 && frame(c.s + c.dir * d).w >= 0.4) d += 8;
          if (d < 200) {
            c.end = d;                                    // the outer lanes end d metres ahead
            if (F.w < 0.999 && c.lc <= 0) {
              if (laneFree(c, laneOff(1, F)) || d < 6) { c.lane = 1; c.lc = 3; c.end = 1e9; } else c.lc = 0.4;
            }
          }
        } else if (c.lc <= 0 && c.gap < 25 && c.vl < c.v0 * 0.7 && c.stop <= 0) {
          const l = c.lane === 0 ? 1 : 0;
          if (laneFree(c, laneOff(l, F))) { c.lane = l; c.lc = 4 + rand2() * 4; } else c.lc = 1;
        }
        if (c.lane >= 2 && c.lc <= 0 && c.gap < 25 && c.vl < c.v0 * 0.7 && c.stop <= 0 && c.end > 300) {
          const l = c.lane === 2 ? 3 : 2;
          if (laneFree(c, laneOff(l, F))) { c.lane = l; c.lc = 4 + rand2() * 4; } else c.lc = 1;
        }
        c.want = laneOff(c.lane, F) + c.wob;
      }
      // leaders: per direction, sorted by progress; a vehicle moving across counts in both lanes
      for (const dir of [1, -1]) {
        const list = cars.filter(c => c.dir === dir).map(c => ({ c, p: dir * rel(c.s) })).sort((a, b) => a.p - b.p);
        const busP = dir * rel(busS), busLat = dir * busO;    // the bus in this direction's frame
        for (let i = 0; i < list.length; i++) {
          const { c, p } = list[i];
          let gap = 1e9, vl = c.v0;
          for (let j = i + 1; j < Math.min(list.length, i + 25); j++) {
            const o = list[j], lim = (o.c.t.Wd + c.t.Wd) / 2 + 0.35;
            if (Math.min(Math.abs(o.c.lat - c.lat), Math.abs(o.c.want - c.lat), Math.abs(o.c.lat - c.want)) < lim) { gap = o.p - p - (o.c.t.L + c.t.L) / 2; vl = o.c.v; break; }
          }
          const bg = busP - p - (11 + c.t.L) / 2;
          if (bg > -8 && bg < gap && Math.abs(busLat - c.lat) < (2.5 + c.t.Wd) / 2 + 0.4) { gap = Math.max(0.1, bg); vl = Math.max(0, dir * busV); }
          if (c.end - c.t.L / 2 - 1 < gap) { gap = Math.max(0.1, c.end - c.t.L / 2 - 1); vl = 0; }   // wait at the end of the lane
          c.gap = gap; c.vl = vl;
        }
      }
      for (const c of cars) {
        // intelligent driver model
        const bike = c.t.name === 'bike', s0 = bike ? 1.2 : 2.2, Th = bike ? 0.8 : 1.3, b = 3.0;
        const ss = s0 + Math.max(0, c.v * Th + c.v * (c.v - c.vl) / (2 * Math.sqrt(c.t.a * b)));
        let acc = c.t.a * (1 - Math.pow(c.v / c.v0, 4) - Math.pow(ss / Math.max(0.1, c.gap), 2));
        if (c.stop > 0) { c.stop -= dt; acc = -8; }
        acc = Math.max(-8, Math.min(c.t.a, acc));
        c.brake = acc < -0.6 || c.v < 0.3;
        c.v = Math.max(0, c.v + acc * dt);
        c.s = ((c.s + c.dir * c.v * dt) % LOOP + LOOP) % LOOP;
        const F = frame(c.s);
        const want = laneOff(c.lane, F) + c.wob;            // the outer lanes squeeze in where they taper
        c.want = want;
        const minLat = M0 + 0.35 + c.t.Wd / 2, maxLat = (c.lane >= 2 ? I1 + (r.sep + CW) * F.w : I1) - 0.35 - c.t.Wd / 2;
        c.lat += Math.max(-1.3 * dt, Math.min(1.3 * dt, want - c.lat));
        c.lat = Math.min(Math.max(c.lat, minLat), Math.max(minLat, maxLat));
        // recycle the ones left far behind or far ahead to the edges of the window
        if (Math.abs(rel(c.s)) > WIN + 40) place(c, busS + (rand2() < 0.5 ? 1 : -1) * (WIN - rand2() * 80));
      }
      // pose, lamps and colliders
      const night = ktmNight() > 0.2;
      for (const c of cars) {
        const F = frame(c.s), o = c.dir * c.lat;
        const x = F.x - F.ty * o, y = F.y + F.tx * o;
        const hx = F.tx * c.dir, hy = F.ty * c.dir, yaw = Math.atan2(hy, hx);
        const up = c.lane < 2, y0 = up ? flyH(c.s) : 0, pitch = up ? Math.atan((flyH(c.s + c.dir * 2) - flyH(c.s - c.dir * 2)) / 4) : 0;
        q4.setFromAxisAngle(Yax, yaw).multiply(qP.setFromAxisAngle(Zax, pitch));
        m4.compose(p4.set(x, y0, -y), q4, one);
        c.t.mBody.setMatrixAt(c.i, m4); c.t.mDet.setMatrixAt(c.i, m4); c.t.mHead.setMatrixAt(c.i, m4); c.t.mTail.setMatrixAt(c.i, m4);
        c.t.mTail.setColorAt(c.i, c.brake ? tailCol.setRGB(3, 0.15, 0.08) : night ? tailCol.setRGB(1.2, 0.05, 0.03) : tailCol.setRGB(0.45, 0.03, 0.03));
        c.t.mHead.setColorAt(c.i, night ? headCol.setRGB(3, 2.9, 2.6) : headCol.setRGB(0.85, 0.85, 0.82));
        // a kinematic collider while near the bus; a knock stops the vehicle for a few seconds
        const near = (x - bp.x) ** 2 + (-y - bp.z) ** 2 < 70 * 70;
        if (near && !c.body) {
          c.body = new CANNON.Body({ mass: 0, type: CANNON.Body.KINEMATIC, shape: new CANNON.Box(new CANNON.Vec3(c.t.L / 2, c.t.Hh / 2, c.t.Wd / 2)) });
          c.body.addEventListener('collide', e => { if (e.body === bus.chassis) { c.stop = 3 + Math.random() * 3; c.v = 0; } });
          world.addBody(c.body);
        } else if (!near && c.body) { world.removeBody(c.body); c.body = null; }
        if (c.body) {
          c.body.position.set(x, y0 + c.t.Hh / 2, -y);
          c.body.quaternion.set(q4.x, q4.y, q4.z, q4.w);
          c.body.velocity.set(hx * c.v, 0, -hy * c.v);
        }
      }
      for (const t of TYPES) {
        for (const m of [t.mBody, t.mDet, t.mHead, t.mTail]) m.instanceMatrix.needsUpdate = true;
        t.mTail.instanceColor.needsUpdate = true; t.mHead.instanceColor.needsUpdate = true;
      }
    };

    // start: Kalanki, heading for Balkhu in the outer carriageway (drive on the left)
    {
      const pB = places.find(p => p.en === 'Balkhu'), ks = r.start;
      const dirB = pB && ((pB.s - S[ks] + LOOP) % LOOP) < LOOP / 2 ? 1 : -1;
      const k = wrap(ks + dirB * Math.round(80 / r.step));
      const o = dirB * (S1(k) + r.shoulder / 2 + r.lane / 2);
      KTM.start = { x: pts[k][0] + N[k][0] * o, z: -(pts[k][1] + N[k][1] * o), heading: Math.atan2(dirB * TG[k][0], -dirB * TG[k][1]) };
    }
    chunkStream(KTM.start.x, KTM.start.z, true);
    busS = locate(KTM.start.x, -KTM.start.z).s;
    for (const c of cars) place(c, busS + (rand2() * 2 - 1) * WIN);
    KTM.ready = true;
    placeBusAtStart();
  }

  const fl = new THREE.FileLoader();
  fl.setResponseType('json');
  fl.load('ktm_map.json', build, undefined, err => console.error('map failed', err));
}
function placeBusAtStart() {
  if (!KTM.ready || !bus) return;
  KTM.stream(KTM.start.x, KTM.start.z);
  bus.reset(KTM.start.x, KTM.start.z, KTM.start.heading);
  snap = true;
}
