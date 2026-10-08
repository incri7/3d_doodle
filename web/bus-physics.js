// Agni coach vehicle physics (cannon-es). Pure simulation, no rendering, so
// the same code runs in the browser and in headless tuning tests.
//
// Frame: the bus's own space matches the glTF model. +Z forward, +Y up,
// +X the door side (the driver's left; Nepal drives on the left), origin on
// the ground under the middle of the bus.
import * as CANNON from 'cannon-es';

export const G = 9.81;
export const STEP = 1 / 120;          // physics sub-step (s)

export const BUS = {
  mass: 12000,                          // kg, laden 11 m coach
  com: [0, 1.5, -0.2],                  // centre of mass (m): high-deck coach, laden; tips at ~0.6 g
  wheelRadius: 0.53,
  restLength: 0.32,                     // suspension
  stiffness: 28,                        // per kg of chassis: sag = g / (6 * k) = 5.8 cm (air suspension)
  dampRelax: 2.2, dampComp: 3.2,        // soft air suspension: the body sways
  travel: 0.2,
  rollInfluence: 1.0,                   // 1 = physical: tyre forces act at the road, full roll moment
  wheels: [                             // centres in bus space
    { name: 'wheel_fl',  x:  1.00, z:  3.15, front: true },
    { name: 'wheel_fr',  x: -1.00, z:  3.15, front: true },
    { name: 'wheel_ril', x:  0.78, z: -2.65, drive: true },
    { name: 'wheel_rir', x: -0.78, z: -2.65, drive: true },
    { name: 'wheel_rol', x:  1.10, z: -2.65, drive: true },
    { name: 'wheel_ror', x: -1.10, z: -2.65, drive: true },
  ],
  wheelbase: 5.8, track: 2.0,
  idle: 650, redline: 2500, peakTorque: 1150,   // Nm, 6-cylinder diesel
  gears: [6.2, 3.9, 2.55, 1.75, 1.28, 1.0], reverse: 5.8, final: 4.3, efficiency: 0.86,
  upshift: 2000, downshift: 1050, shiftTime: 0.45,
  governor: 30.5,                       // m/s, 110 km/h (Nepali buses rarely respect the 80 limit)
  brakeDecel: 9.5,                      // m/s^2 brake demand, more than the tyres can give: no ABS, wheels slide
  engineBrake: 0.45,                    // m/s^2 when coasting in gear
  cdA: 0.62 * 7.6,                      // drag coefficient x frontal area (m^2)
  rollRes: 0.009,
  maxSteer: 0.5, returnRate: 2.5,       // road-wheel lock (rad); return speed in locks per second
  fullInputG: 0.85,                     // full input at speed asks for about the tyres' limit
  muPeak: 0.85, muLocked: 0.62,         // longitudinal tyre grip: rolling vs locked (sliding)
  grip: { road: 1.3, offroad: 0.75 },   // tyre friction (frictionSlip), about 0.8 g on asphalt
  roadHalfWidth: 5,                     // the road runs along world Z at x = 0
  onRoad: null,                         // optional (x, z) => bool for maps with curved roads
};

/** Torque curve: a fat diesel mid-range that falls away near the redline. */
export function torqueAt(rpm) {
  const { idle, peakTorque: T } = BUS;
  if (rpm < idle) return 0.55 * T;
  if (rpm < 1150) return T * (0.62 + 0.38 * (rpm - idle) / (1150 - idle));
  if (rpm < 1750) return T;
  return T * Math.max(0.15, 1 - 0.55 * (rpm - 1750) / 750);
}

export function createWorld() {
  const world = new CANNON.World({ gravity: new CANNON.Vec3(0, -G, 0) });
  world.broadphase = new CANNON.SAPBroadphase(world);
  world.allowSleep = true;
  world.defaultContactMaterial.friction = 0.45;
  world.defaultContactMaterial.restitution = 0.15;
  world.solver.iterations = 12;
  // A huge flat box rather than CANNON.Plane: SAPBroadphase mishandles the
  // plane's infinite bounds in ray queries, so suspension rays miss it.
  const ground = new CANNON.Body({ mass: 0, shape: new CANNON.Box(new CANNON.Vec3(4000, 1, 4000)) });
  ground.position.set(0, -1, 0);
  world.addBody(ground);
  world.ground = ground;
  return world;
}

export function staticBox(world, half, pos, yaw = 0) {
  const b = new CANNON.Body({ mass: 0, shape: new CANNON.Box(new CANNON.Vec3(...half)) });
  b.position.set(...pos);
  b.quaternion.setFromEuler(0, yaw, 0);
  world.addBody(b);
  return b;
}

export function staticCylinder(world, r, h, pos) {
  const b = new CANNON.Body({ mass: 0, shape: new CANNON.Cylinder(r, r, h, 8) });
  b.position.set(...pos);
  world.addBody(b);
  return b;
}

export function dynamicBody(world, shape, mass, pos, opts = {}) {
  const b = new CANNON.Body({ mass, shape, linearDamping: 0.05, angularDamping: 0.1, ...opts });
  b.position.set(...pos);
  b.sleepSpeedLimit = 0.2;
  world.addBody(b);
  return b;
}

/**
 * colliders: [{ half: [x, y, z], pos: [x, y, z], quat: [x, y, z, w] }] boxes in
 * bus space (from the model's COL-* nodes).
 */
export class Bus {
  constructor(world, colliders) {
    const com = new CANNON.Vec3(...BUS.com);
    this.com = com;
    const chassis = new CANNON.Body({ mass: BUS.mass, angularDamping: 0.01, linearDamping: 0.001 });
    for (const c of colliders) {
      const off = new CANNON.Vec3(c.pos[0] - com.x, c.pos[1] - com.y, c.pos[2] - com.z);
      chassis.addShape(new CANNON.Box(new CANNON.Vec3(...c.half)), off, new CANNON.Quaternion(...c.quat));
    }
    // A long bus is far stiffer in yaw/pitch than a uniform box of its hull.
    chassis.updateMassProperties();
    chassis.allowSleep = false;
    this.chassis = chassis;

    const vehicle = new CANNON.RaycastVehicle({ chassisBody: chassis, indexRightAxis: 0, indexUpAxis: 1, indexForwardAxis: 2 });
    const sag = G / (BUS.wheels.length * BUS.stiffness);
    for (const w of BUS.wheels) {
      vehicle.addWheel({
        radius: BUS.wheelRadius,
        directionLocal: new CANNON.Vec3(0, -1, 0),
        axleLocal: new CANNON.Vec3(1, 0, 0),
        suspensionStiffness: BUS.stiffness,
        suspensionRestLength: BUS.restLength,
        dampingRelaxation: BUS.dampRelax,
        dampingCompression: BUS.dampComp,
        maxSuspensionForce: BUS.mass * G * 3,
        maxSuspensionTravel: BUS.travel,
        rollInfluence: BUS.rollInfluence,
        frictionSlip: BUS.grip.road,
        useCustomSlidingRotationalSpeed: true,
        customSlidingRotationalSpeed: -30,
        chassisConnectionPointLocal: new CANNON.Vec3(
          w.x - com.x, BUS.wheelRadius + BUS.restLength - sag - com.y, w.z - com.z),
      });
    }
    vehicle.addToWorld(world);
    this.vehicle = vehicle;
    this.world = world;

    this.gear = 0;            // 0 neutral, 1..6 forward, -1 reverse
    this.shiftTimer = 0;
    this.rpm = BUS.idle;
    this.steer = 0;           // road-wheel angle (rad), + turns toward +X
    this.speed = 0;           // forward speed (m/s), negative when reversing
    this.throttle = 0;
    this.braking = false;
    this.locked = 0;          // wheels currently locked under braking
    this.impact = 0;          // last hard-impact speed, for sound/camera shake
    chassis.addEventListener('collide', e => {
      const v = Math.abs(e.contact.getImpactVelocityAlongNormal());
      if (v > this.impact) this.impact = v;
    });
    this.reset(0, 0, 0);
  }

  /** Place the bus upright at (x, z) facing `heading` (0 = +Z), at rest. */
  reset(x, z, heading) {
    const c = this.chassis;
    const q = new CANNON.Quaternion().setFromEuler(0, heading, 0);
    const comWorld = q.vmult(this.com);
    c.position.set(x + comWorld.x, comWorld.y + 0.05, z + comWorld.z);
    c.quaternion.copy(q);
    c.velocity.setZero(); c.angularVelocity.setZero();
    this.gear = 0; this.rpm = BUS.idle; this.steer = 0;
  }

  forward() { return this.chassis.quaternion.vmult(new CANNON.Vec3(0, 0, 1)); }
  heading() { const f = this.forward(); return Math.atan2(f.x, f.z); }
  upright() { return this.chassis.quaternion.vmult(new CANNON.Vec3(0, 1, 0)).y; }

  /** Advance driver inputs and forces by dt (call before world.step).
   *  input: { gas: 0..1, brake: 0..1, steer: -1..1 (+ = toward +X), handbrake } */
  update(dt, input) {
    const c = this.chassis, v = this.vehicle;
    const fwd = this.forward();
    this.speed = c.velocity.dot(fwd);
    const speed = this.speed, aspeed = Math.abs(speed);

    // Steering: rate-limited, less lock at speed, Ackermann geometry.
    // Steering like hands on a wheel: it winds on gradually (a tap is a small
    // correction) and springs back faster. Full input at speed asks for about
    // the tyres' grip limit, which is above the rollover threshold: hold it
    // through a fast corner and the bus goes over.
    const lock = Math.min(BUS.maxSteer, Math.atan(BUS.wheelbase * BUS.fullInputG * G / Math.max(1, aspeed * aspeed)));
    const target = THREEish.clamp(input.steer, -1, 1) * lock;
    const returning = Math.abs(target) < Math.abs(this.steer) || Math.sign(target) !== Math.sign(this.steer);
    // about 0.8 s from centre to full input at any speed; springs back faster
    const maxDelta = (returning ? Math.max(BUS.returnRate * lock, 0.25) : Math.max(lock / 0.8, 0.05)) * dt;
    this.steer += THREEish.clamp(target - this.steer, -maxDelta, maxDelta);
    const d = this.steer;
    let inner = d, outer = d;
    if (Math.abs(d) > 1e-4) {
      const R = BUS.wheelbase / Math.tan(Math.abs(d));
      inner = Math.sign(d) * Math.atan(BUS.wheelbase / (R - BUS.track / 2));
      outer = Math.sign(d) * Math.atan(BUS.wheelbase / (R + BUS.track / 2));
    }
    // + steer turns toward +X (the driver's left), so the +X wheel (index 0)
    // is the inner one. Verified in the browser: A must move the bus toward +X.
    v.setSteeringValue(d > 0 ? inner : outer, 0);
    v.setSteeringValue(d > 0 ? outer : inner, 1);

    // Gear selection (automatic, with reverse on S at a standstill).
    const wantForward = input.gas > 0, wantBack = input.brake > 0;
    let brake = 0, drive = 0;
    if (wantForward) {
      if (this.gear === -1 && speed < -0.6) brake = 1;          // rolling back: W brakes first
      else { if (this.gear <= 0) this.gear = 1; drive = input.gas; }
    } else if (wantBack) {
      if (speed > 0.6) brake = input.brake;                     // moving forward: S brakes
      else { this.gear = -1; drive = input.brake; }
    } else if (aspeed < 0.3 && this.gear > 0) this.gear = 0;
    this.braking = brake > 0;

    // Engine speed follows the wheels; the clutch slips below ~idle road speed.
    const ratio = this.gear === -1 ? BUS.reverse : this.gear > 0 ? BUS.gears[this.gear - 1] : 0;
    const wheelRpm = aspeed / BUS.wheelRadius * 60 / (2 * Math.PI);
    let rpm = ratio ? wheelRpm * ratio * BUS.final : BUS.idle;
    if (rpm < BUS.idle + drive * 900) rpm = BUS.idle + drive * 900 * (ratio ? 1 : 0.6);
    this.rpm += (Math.min(rpm, BUS.redline + 150) - this.rpm) * Math.min(1, dt * 10);

    // Automatic shifts with a short torque cut.
    this.shiftTimer = Math.max(0, this.shiftTimer - dt);
    if (this.gear > 0 && this.shiftTimer === 0) {
      if (this.rpm > BUS.upshift && this.gear < BUS.gears.length && drive > 0) { this.gear++; this.shiftTimer = BUS.shiftTime; }
      else if (this.rpm < BUS.downshift && this.gear > 1) { this.gear--; this.shiftTimer = BUS.shiftTime * 0.6; }
    }

    // Wheel force from torque through the driveline, split over the driven wheels.
    let force = 0;
    if (drive > 0 && ratio && this.shiftTimer === 0) {
      force = torqueAt(this.rpm) * ratio * BUS.final * BUS.efficiency / BUS.wheelRadius * drive;
      if (this.gear > 0 && speed > BUS.governor) force = 0;                // speed limiter
      if (this.gear === -1 && speed < -4.5) force = 0;                     // reverse limit ~16 km/h
      if (this.rpm >= BUS.redline) force *= 0.2;
      if (this.gear === -1) force = -force;
    }
    const driven = BUS.wheels.filter(w => w.drive).length;

    // Brakes act as an impulse cap per sub-step; split evenly over all six wheels.
    const perWheel = BUS.mass / BUS.wheels.length;
    const brakeDemand = brake * perWheel * BUS.brakeDecel * STEP;
    this.locked = 0;
    this.wheelLock = this.wheelLock || [];
    const coast = !drive && !brake;
    BUS.wheels.forEach((w, i) => {
      const info = v.wheelInfos[i];
      // No ABS: each tyre can only brake up to its grip (load x mu). Ask for
      // more and the wheel locks: it slides with less grip and, at the front,
      // stops steering.
      const cap = info.suspensionForce * STEP * BUS.muPeak;
      const lockedWheel = brakeDemand > cap && info.isInContact && aspeed > 1;
      const rearLocked = input.handbrake && !w.front && aspeed > 1;
      let b = lockedWheel ? info.suspensionForce * STEP * BUS.muLocked : brakeDemand;
      if (lockedWheel) this.locked++;
      this.wheelLock[i] = lockedWheel || (rearLocked && info.isInContact);
      if (coast) b = perWheel * (G * BUS.rollRes + (this.gear > 0 ? BUS.engineBrake : 0)) * STEP;
      if (rearLocked) b = Math.max(b, info.suspensionForce * STEP * BUS.muLocked);
      // Grip: asphalt vs verge; the handbrake lets the rear step out a little.
      const p = info.raycastResult.hitPointWorld;
      const onRoad = info.isInContact && (BUS.onRoad ? BUS.onRoad(p.x, p.z) : Math.abs(p.x) < BUS.roadHalfWidth);
      info.frictionSlip = (onRoad ? BUS.grip.road : BUS.grip.offroad) * (lockedWheel || rearLocked ? 0.35 : 1);
      if (!onRoad && info.isInContact && coast) b *= 2.5;
      // cannon-es pushes along -forward for positive force in this axis setup
      v.applyEngineForce(w.drive ? -force / driven : 0, i);
      v.setBrake(force ? 0 : b, i);
    });

    // Aerodynamic drag on the body.
    const vel = c.velocity, sp = vel.length();
    if (sp > 0.1) {
      const k = -0.5 * 1.2 * BUS.cdA * sp;
      c.applyForce(new CANNON.Vec3(vel.x * k, vel.y * k, vel.z * k), c.position);
    }
  }

  /** Per-wheel state for animating the model: spin angle, steer, centre drop. */
  /** Wheels currently off the ground (2+ on one side = tipping). */
  liftedWheels() { return this.vehicle.wheelInfos.filter(w => !w.isInContact).length; }

  wheelStates() {
    const sag = G / (BUS.wheels.length * BUS.stiffness);
    return this.vehicle.wheelInfos.map((w, i) => ({
      name: BUS.wheels[i].name,
      spin: -w.rotation,        // + = rolling forward
      steer: w.steering,        // + = toward +X
      // + = wheel sits lower than the modelled position (suspension extended)
      drop: (w.suspensionLength - (BUS.restLength - sag)),
      contact: w.isInContact,
      // tyre sliding (locked under braking, or past its grip sideways): skid marks, smoke
      skid: w.isInContact && ((this.wheelLock && this.wheelLock[i]) || w.skidInfo < 0.75),
      onRoad: BUS.onRoad ? BUS.onRoad(w.raycastResult.hitPointWorld.x, w.raycastResult.hitPointWorld.z)
        : Math.abs(w.raycastResult.hitPointWorld.x) < BUS.roadHalfWidth,
      contactPoint: w.raycastResult.hitPointWorld,
    }));
  }

  get kmh() { return this.speed * 3.6; }
  get gearLabel() { return this.gear === -1 ? 'R' : this.gear === 0 ? 'N' : String(this.gear); }
}

const THREEish = { clamp: (x, a, b) => Math.max(a, Math.min(b, x)) };
