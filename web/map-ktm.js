// Kathmandu Ring Road map (Kalanki - Balkhu) for the driving page.
// Inlined into drive.html by web/make_drive.py at the "@@map" marker, so it
// shares the page's module scope (THREE, CANNON, scene, world, bus, ...).
// Data: ktm_map.json from world/export_web.py (OpenStreetMap, Google Open
// Buildings, Copernicus DEM, Sentinel-2). Map x = east, y = north; three.js
// X = x, Z = -y. The playable world is flat; hills rise away from the road.
const KTM = { ready: false, start: null, lights: [], stream: () => {} };
// Collider streaming: thousands of static bodies make every physics step
// scan them all, so only those within ~100 m of the bus are in the world.
const KTM_CELL = 50, KTM_REACH = 2;
const ktmCells = new Map(), ktmActive = new Set();
function poolAdd(b) {
  const key = Math.floor(b.position.x / KTM_CELL) + ',' + Math.floor(b.position.z / KTM_CELL);
  if (!ktmCells.has(key)) ktmCells.set(key, []);
  ktmCells.get(key).push(b);
}
function poolBox(half, pos, yaw = 0) {
  const b = new CANNON.Body({ mass: 0, shape: new CANNON.Box(new CANNON.Vec3(...half)) });
  b.position.set(...pos); b.quaternion.setFromEuler(0, yaw, 0); poolAdd(b);
}
function poolCyl(r, h, pos) {
  const b = new CANNON.Body({ mass: 0, shape: new CANNON.Cylinder(r, r, h, 8) });
  b.position.set(...pos); poolAdd(b);
}
let ktmLastCell = null;
KTM.stream = (x, z) => {
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
};
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
  const kerb = new THREE.MeshStandardMaterial({ map: kerbTex, roughness: 0.6 });
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
  const signCanvases = [];
  for (let i = 0; i < 16; i++) {
    const c = document.createElement('canvas'); c.width = 512; c.height = 72; drawSign(c, i);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = MAX_ANISO;
    signCanvases.push({ c, t, i });
    signMats.push(new THREE.MeshStandardMaterial({ map: t, roughness: 0.5 }));
  }
  document.fonts && document.fonts.ready.then(() => signCanvases.forEach(s => { drawSign(s.c, s.i); s.t.needsUpdate = true; }));

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
    mesh(mat, shadow = true) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(this.p, 3));
      g.setAttribute('uv', new THREE.Float32BufferAttribute(this.uv, 2));
      if (this.c.length) g.setAttribute('color', new THREE.Float32BufferAttribute(this.c, 3));
      g.setIndex(this.i);
      g.computeVertexNormals();
      const m = new THREE.Mesh(g, mat);
      m.castShadow = m.receiveShadow = shadow;
      scene.add(m);
      return m;
    }
  }

  function build(D) {
    const r = D.road;
    const M0 = r.median / 2, CW = 2 * r.lane + r.shoulder, I1 = M0 + CW, S1 = I1 + r.sep, EDGE = S1 + CW, FOOT = r.foot;
    const pts = [];
    for (let k = 0; k < r.pts.length; k += 2) pts.push([r.pts[k], r.pts[k + 1]]);
    const n = pts.length, S = [0], T = [], N = [];
    for (let k = 1; k < n; k++) S.push(S[k - 1] + Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]));
    for (let k = 0; k < n; k++) {
      const a = pts[Math.max(0, k - 1)], b = pts[Math.min(n - 1, k + 1)];
      const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
      T.push([(b[0] - a[0]) / L, (b[1] - a[1]) / L]); N.push([-T[k][1], T[k][0]]);
    }
    const at = (k, o, h) => P2(pts[k][0] + N[k][0] * o, pts[k][1] + N[k][1] * o, h);
    // --- road surfaces ------------------------------------------------------
    function strip(o0, o1, h0, h1, mat, uscale, vscale, k0 = 0, k1 = n - 1) {
      if (o0 > o1) [o0, o1, h0, h1] = [o1, o0, h1, h0];      // keep faces pointing up
      const g = new Geo();
      for (let k = k0; k < k1; k++) {
        g.quad(at(k, o0, h0), at(k + 1, o0, h0), at(k + 1, o1, h1), at(k, o1, h1),
          [S[k] / uscale, o0 / vscale + h0], [S[k + 1] / uscale, o0 / vscale + h0], [S[k + 1] / uscale, o1 / vscale + h1], [S[k] / uscale, o1 / vscale + h1]);
      }
      const m = g.mesh(mat, false); m.receiveShadow = true;
      if (o0 === o1) m.material.side = THREE.DoubleSide;
      return m;
    }
    const kerbFace = (o, h) => { const m = strip(o, o, 0, h, kerb, 2, 1); return m; };
    for (const sg of [1, -1]) {
      for (const [lo, hi] of [[M0, I1], [S1, EDGE]]) {
        strip(sg * lo, sg * hi, 0, 0, asphalt, 8, 8);
        for (const off of [lo + 0.3, hi - 0.3]) strip(sg * (off - 0.06), sg * (off + 0.06), 0.008, 0.008, yellow, 1, 1);
        // lane dashes 3 m on, 6 m off
        const g = new Geo(), mid = lo + r.shoulder / 2 + r.lane;
        for (let s = 0; s < S[n - 1] - 3; s += 9) {
          const k = S.findIndex(v => v >= s), k2 = S.findIndex(v => v >= s + 3);
          if (k < 0 || k2 < 0) break;
          g.quad(at(k, sg * (mid - 0.07), 0.01), at(k2, sg * (mid - 0.07), 0.01), at(k2, sg * (mid + 0.07), 0.01), at(k, sg * (mid + 0.07), 0.01), [0, 0], [1, 0], [1, 1], [0, 1]);
        }
        g.mesh(whiteP, false).receiveShadow = true;
      }
      strip(sg * I1, sg * S1, 0.25, 0.25, medianMat, 2, 2);
      kerbFace(sg * I1, 0.25); kerbFace(sg * S1, 0.25); kerbFace(sg * M0, 0.25); kerbFace(sg * EDGE, 0.2);
      strip(sg * EDGE, sg * (EDGE + FOOT), 0.2, 0.2, pavers, 1.3, 1.3);
      strip(sg * (EDGE + FOOT), sg * (EDGE + FOOT + 4), 0.2, -0.05, vergeMat, 3, 3);
    }
    strip(-M0, M0, 0.25, 0.25, medianMat, 2, 2);
    // bridge parapets over the Balkhu Khola
    const kb0 = S.findIndex(v => v >= r.bridge[0]), kb1 = S.findIndex(v => v >= r.bridge[1]);
    const rail = new THREE.MeshStandardMaterial({ color: 0x8c8a84, roughness: 0.7, side: THREE.DoubleSide });
    if (kb0 > 0 && kb1 > kb0) for (const sg of [1, -1]) strip(sg * (EDGE + FOOT), sg * (EDGE + FOOT), 0.2, 1.3, rail, 2, 1, kb0, kb1);

    // --- road colliders: median, separators, footpaths, bridge parapets ------------
    const seg = 2;   // points per collider (8 m)
    for (let k = 0; k + seg < n; k += seg) {
      const a = pts[k], b = pts[k + seg];
      const cx = (a[0] + b[0]) / 2, cy = (a[1] + b[1]) / 2, len = Math.hypot(b[0] - a[0], b[1] - a[1]) / 2 + 0.3;
      const tx = (b[0] - a[0]) / (2 * len - 0.6), ty = (b[1] - a[1]) / (2 * len - 0.6), nx = -ty, ny = tx;
      const yaw = Math.atan2(ty, tx);
      const add = (o, hw, h) => poolBox( [len, h / 2, hw], [cx + nx * o, h / 2, -(cy + ny * o)], yaw);
      add(0, M0, 0.25);
      for (const sg of [1, -1]) {
        add(sg * (I1 + S1) / 2, r.sep / 2, 0.25);
        add(sg * (EDGE + FOOT / 2), FOOT / 2, 0.2);
        if (S[k] >= r.bridge[0] && S[k] <= r.bridge[1]) add(sg * (EDGE + FOOT), 0.15, 1.3);
      }
    }

    // --- on-road test for tyre grip (2 m grid) ----------------------------------
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    const gx0 = Math.min(...xs) - 30, gy0 = Math.min(...ys) - 30, GW = Math.ceil((Math.max(...xs) + 30 - gx0) / 2), GH = Math.ceil((Math.max(...ys) + 30 - gy0) / 2);
    const grid = new Uint8Array(GW * GH);
    for (let k = 0; k < n - 1; k++) for (let f = 0; f < 1; f += 0.25) for (let o = -EDGE; o <= EDGE; o += 0.8) {
      const x = pts[k][0] * (1 - f) + pts[k + 1][0] * f + N[k][0] * o, y = pts[k][1] * (1 - f) + pts[k + 1][1] * f + N[k][1] * o;
      const i = Math.floor((x - gx0) / 2), j = Math.floor((y - gy0) / 2);
      if (i >= 0 && j >= 0 && i < GW && j < GH) grid[j * GW + i] = 1;
    }
    BUS.onRoad = (x, z) => {
      const i = Math.floor((x - gx0) / 2), j = Math.floor((-z - gy0) / 2);
      return i >= 0 && j >= 0 && i < GW && j < GH && grid[j * GW + i] === 1;
    };

    // --- terrain (DEM, flattened by the road) with the satellite image -------------
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

    // --- near buildings: windows, shops, signboards, balconies, water tanks ----------
    const wallsG = new Geo(), shopG = new Geo(), roofG = new Geo(), extraG = new Geo();
    const signG = signMats.map(() => new Geo());
    const tanks = [];
    const nearest = (x, y) => {      // nearest centreline point index (coarse then fine)
      let best = 0, bd = 1e18;
      for (let k = 0; k < n; k += 5) { const d = (pts[k][0] - x) ** 2 + (pts[k][1] - y) ** 2; if (d < bd) { bd = d; best = k; } }
      for (let k = Math.max(0, best - 5); k < Math.min(n, best + 6); k++) { const d = (pts[k][0] - x) ** 2 + (pts[k][1] - y) ** 2; if (d < bd) { bd = d; best = k; } }
      return [best, Math.sqrt(bd)];
    };
    let hash = 1;
    const rand = () => (hash = (hash * 16807) % 2147483647) / 2147483647;
    for (const b of D.near) {
      const ring = [];
      for (let k = 0; k < b.p.length; k += 2) ring.push([b.p[k], b.p[k + 1]]);
      const H = b.f * 2.9 + 0.5;
      const col = WALL_COLS[b.c % WALL_COLS.length].clone().multiplyScalar(0.85 + (b.c % 31) / 100);
      let per = 0;
      const [, dist] = nearest(b.b[0], b.b[1]);
      for (let j = 0; j < ring.length; j++) {
        const a = ring[j], c = ring[(j + 1) % ring.length];
        const L = Math.hypot(c[0] - a[0], c[1] - a[1]);
        if (L < 0.05) continue;
        const ox = (c[1] - a[1]) / L, oy = -(c[0] - a[0]) / L;       // outward (CCW ring)
        const mx = (a[0] + c[0]) / 2, my = (a[1] + c[1]) / 2;
        const [k] = nearest(mx, my);
        const tx = pts[k][0] - mx, ty = pts[k][1] - my, tl = Math.hypot(tx, ty) || 1;
        const facing = (ox * tx + oy * ty) / tl > 0.6;
        const shop = facing && dist < 45 && L > 2.5;
        const u0 = per / 3.1, u1 = (per + L) / 3.1;
        const A = (h) => P2(a[0], a[1], h), C = (h) => P2(c[0], c[1], h);
        (shop ? shopG : wallsG).quad(A(-0.5), C(-0.5), C(2.9), A(2.9), [u0 * 1.5, 0], [u1 * 1.5, 0], [u1 * 1.5, 1], [u0 * 1.5, 1], shop ? null : col);
        wallsG.quad(A(2.9), C(2.9), C(H), A(H), [u0, 1], [u1, 1], [u1, H / 2.9], [u0, H / 2.9], col);
        per += L;
        const ax = [(c[0] - a[0]) / L, -(c[1] - a[1]) / L], az = [ox, -oy];       // three.js x/z of along and outward
        if (shop && rand() < 0.85) {
          const w = Math.min(L - 0.4, 6), si = Math.floor(rand() * signMats.length);
          const cx = mx + ox * 0.14, cy = my + oy * 0.14;
          extraG.box(cx, 3.25, -cy, ax, az, w / 2, 0.38, 0.06, new THREE.Color(0x222222));
          const p0 = P2(cx + ox * 0.07 - (c[0] - a[0]) / L * w / 2, cy + oy * 0.07 - (c[1] - a[1]) / L * w / 2, 2.9);
          const p1 = P2(cx + ox * 0.07 + (c[0] - a[0]) / L * w / 2, cy + oy * 0.07 + (c[1] - a[1]) / L * w / 2, 2.9);
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
      // collider: oriented box
      poolBox( [b.b[2] / 2, H / 2, b.b[3] / 2], [b.b[0], H / 2, -b.b[1]], b.b[4]);
    }
    wallsG.mesh(walls); shopG.mesh(shutters); roofG.mesh(roofMat, false);
    extraG.mesh(new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.7, side: THREE.DoubleSide }), false);
    signG.forEach((g, i) => { if (g.i.length) g.mesh(signMats[i], false); });
    {
      const tm = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.6, 0.6, 1.25, 14), new THREE.MeshStandardMaterial({ color: 0x0b0b0c, roughness: 0.4 }), tanks.length);
      const m4 = new THREE.Matrix4();
      tanks.forEach((t, i) => { m4.makeTranslation(t[0], t[2] + 0.62, -t[1]); tm.setMatrixAt(i, m4); });
      tm.castShadow = true; scene.add(tm);
    }

    // --- far buildings (boxes on the terrain) ---------------------------------------
    {
      const fm = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0),
        new THREE.MeshStandardMaterial({ roughness: 0.9 }), D.far.length);
      const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3(), Y = new THREE.Vector3(0, 1, 0);
      D.far.forEach((f, i) => {
        const [cx, cy, w, d, a, fl, ci, hb] = f;
        m4.compose(p.set(cx, hb - 0.3, -cy), q.setFromAxisAngle(Y, a), s.set(w, fl * 2.9 + 0.5, d));
        fm.setMatrixAt(i, m4);
        fm.setColorAt(i, WALL_COLS[ci % WALL_COLS.length]);
      });
      fm.castShadow = false; fm.receiveShadow = true; scene.add(fm);
    }

    // --- poles with wires, median street lights, roadside trees ----------------------
    const poleG = new Geo(), lightG = new Geo(), wire = [];
    const grey = new THREE.Color(0x77756f), dark = new THREE.Color(0x333333), lamp = new THREE.Color(0xdddddd);
    for (const sg of [1, -1]) {
      let last = null;
      for (let s = sg > 0 ? 10 : 27; s < S[n - 1] - 10; s += 36) {
        const k = S.findIndex(v => v >= s), o = sg * (EDGE + FOOT - 0.4);
        const x = pts[k][0] + N[k][0] * o, y = pts[k][1] + N[k][1] * o;
        const tz = [T[k][0], -T[k][1]], nz = [N[k][0] * sg, -N[k][1] * sg];
        poleG.box(x, 4.6, -y, tz, nz, 0.12, 4.6, 0.12, grey);
        poleG.box(x, 8.6, -y, tz, nz, 0.9, 0.05, 0.06, dark);
        poolBox( [0.15, 4.6, 0.15], [x, 4.6, -y]);
        const tops = [-0.8, -0.3, 0.3, 0.8].map(d => new THREE.Vector3(x + T[k][0] * d, 8.65, -(y + T[k][1] * d)));
        if (last) for (let w = 0; w < 4; w++) for (const drop of [0, 0.25]) {
          let prev = null;
          for (let f = 0; f <= 1.0001; f += 0.125) {
            const v = last[w].clone().lerp(tops[w], f); v.y -= (0.9 + drop) * 4 * f * (1 - f) + drop;
            if (prev) wire.push(prev, v);
            prev = v;
          }
        }
        last = tops;
      }
    }
    poleG.mesh(new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.8, side: THREE.DoubleSide }), false);
    const wg = new THREE.BufferGeometry().setFromPoints(wire);
    scene.add(new THREE.LineSegments(wg, new THREE.LineBasicMaterial({ color: 0x111111 })));
    for (let s = 20; s < S[n - 1] - 10; s += 32) {
      const k = S.findIndex(v => v >= s), x = pts[k][0], y = pts[k][1];
      const tz = [T[k][0], -T[k][1]];
      lightG.box(x, 5.25, -y, tz, [-tz[1], tz[0]], 0.09, 5.0, 0.09, grey);
      for (const sg of [1, -1]) {
        const nz = [N[k][0] * sg, -N[k][1] * sg];
        lightG.box(x + N[k][0] * sg * 1.0, 10.15, -(y + N[k][1] * sg * 1.0), nz, tz, 1.0, 0.04, 0.04, grey);
        lightG.box(x + N[k][0] * sg * 1.9, 10.07, -(y + N[k][1] * sg * 1.9), nz, tz, 0.35, 0.06, 0.14, lamp);
        KTM.lights.push(new THREE.Vector3(x + N[k][0] * sg * 1.9, 10.0, -(y + N[k][1] * sg * 1.9)));
      }
    }
    lightG.mesh(new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.5, side: THREE.DoubleSide }), false);
    {
      const spots = [];
      for (const sg of [1, -1]) for (let s = 5; s < S[n - 1]; s += 7) {
        if (rand() > 0.35) continue;
        const k = S.findIndex(v => v >= s), o = sg * (EDGE + FOOT + 1 + rand() * 2);
        spots.push([pts[k][0] + N[k][0] * o, pts[k][1] + N[k][1] * o, 0.6 + rand() * 0.6]);
      }
      const tr = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.14, 0.22, 2.4, 7).translate(0, 1.2, 0), new THREE.MeshStandardMaterial({ color: 0x5b4632, roughness: 1 }), spots.length);
      const cr = new THREE.InstancedMesh(broad.geometry, crownMat, spots.length);
      const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s3 = new THREE.Vector3(), p = new THREE.Vector3();
      const c = new THREE.Color();
      spots.forEach(([x, y, k], i) => {
        m4.compose(p.set(x, 0, -y), q, s3.set(k, k, k)); tr.setMatrixAt(i, m4);
        m4.compose(p.set(x, 2.1 * k, -y), q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), rand() * 6.3), s3.set(k, k, k)); cr.setMatrixAt(i, m4);
        cr.setColorAt(i, c.setHSL(0.24 + rand() * 0.08, 0.45, 0.18 + rand() * 0.1));
        poolCyl( 0.28 * k, 2.4 * k, [x, 1.2 * k, -y]);
        q.identity();
      });
      tr.castShadow = cr.castShadow = true;
      scene.add(tr, cr);
    }

    // start: the Kalanki end, heading to Balkhu in the outer lane (drive on the left)
    const ks = n - 1 - Math.round(140 / D.road.step);
    const o = -(S1 + r.shoulder / 2 + r.lane / 2);
    KTM.start = { x: pts[ks][0] + N[ks][0] * o, z: -(pts[ks][1] + N[ks][1] * o), heading: Math.atan2(-T[ks][0], T[ks][1]) };
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
