# A new 3D recipe: try, look, promote

For maintainers, in a checkout. The on-premises 3D set is built from
recipes -- one builder each in the renderer's scene script,
`plugin/src/infragram/iso3d/scene.js` -- and a new recipe goes through three steps:
try it without touching the package, look at the picture and the seat
report, then promote it into the shipped set. A diagram never needs this: it
draws a shipped item, or a recipe with its knobs turned, as the skill's
[compose.md](../../plugin/skills/infragram-architect/references/compose.md)
describes under "Items rendered by spec".

## 1. Is it already buildable?

Most asks are a shipped item or a recipe with its knobs turned. Check
before writing anything:

```python
from infragram.iso3d.vocabulary import recipes
recipes()["server"]   # [('units', 2), ('drivesN', 4), ('rows', 0)]
```

When a recipe fits, the diagram passes a spec (`Iso(..., recipe="tank",
family="facility", glyph="thermo")`) and no builder is written. Write one
only for a shape no recipe makes.

## 2. Write the builder

One arrow function on `R`, in a `.js` file of its own, with the shipped
signature. `fam.colour` is the item's colour, `tex` the badge texture (or
`null` for no badge), and every knob after them has a default:

```js
// A thermal buffer tank on legs: a lagged drum, a top dome, four flanges.
R.buffer_tank = (fam, tex, legs = 4) => {
  const g = new THREE.Group();
  plate7(g, 12, 12);                                    // a ground plate keeps the shadow honest
  for (let i = 0; i < legs; i += 1) { const a = i / legs * Math.PI * 2; g.add(boxMesh(0.6, 3, 0.6, M.post, Math.cos(a) * 2.6, 1.5, Math.sin(a) * 2.6)); }
  g.add(vcyl(3.2, 9, glossAccent(fam.colour), 0, 7.5, 0, 32));
  g.add(sph(3.2, glossAccent(fam.colour), 0, 12, 0, 32));
  for (const y of [5, 8]) g.add(torusMesh(3.25, 0.16, M.paintDark, 0, y, 0, Math.PI / 2));
  g.add(hcyl(0.5, 3, M.metal, -4.4, 6, 0, 12)); g.add(hcyl(0.5, 3, M.metal, 4.4, 9, 0, 12));
  badge(g, tex, 1.6, 0, 7.5, 3.24);                     // the badge on a face the camera sees
  return g;
};
```

What is there to build with, all defined earlier in `scene.js`:

- **Shapes.** `boxMesh(w, h, d, mat, x, y, z)`, `vcyl(r, h, mat, x, y, z)`
  (upright), `hcyl` (along x), `zcyl` (along z), `sph(r, mat, x, y, z)`,
  `coneMesh(r, h, mat, x, y, z)`, `torusMesh(r, tube, mat, x, y, z, rotX, rotY)`,
  `tubeMesh([points], r, mat)`, `bar(g, a, b, r, mat)` between two `V(x, y, z)`
  points, `roundedSlab(w, h, d, radius, mat)`, `chassis(fam, units)` for a
  rack-mount body with `portRow`, `sfpCages`, `drives`, `statusLights`.
- **Placing.** `rot(mesh, x, y, z)`, `scl(mesh, x, y, z)` and `at(mesh, x, y, z)`
  return the mesh, so `g.add(rot(coneMesh(...), Math.PI, 0, 0))` reads as one
  line. `hinged(g, w, h, t, mat, hx, hy, hz, rotY, rotX)` is a door or lid on
  a pivot. Never write `g.add(mesh.rotation.x = ...)`: that adds a number and
  the mesh is never seen.
- **Scenery.** `plate7(g, w, d, mat)` a ground plate, `wallBack(g, w, h)` a
  wall behind, `ladder7`, `building`, `fence`, `lattice`, `insulator`,
  `conductor`, `windTurbine`, `chimney`, `plume`, `light(g, hex, x, y, z)` a
  status LED with its halo, `screen(g, colour, w, h, x, y, z)` a lit panel,
  `badge(g, tex, w, x, y, z, rotY)` the printed badge.
- **Materials.** `M.metal`, `M.paint`, `M.paintDark`, `M.plastic`,
  `M.plasticDark`, `M.glass`, `M.concrete`, `M.wood`, `M.copper`,
  `M.porcelain`, `M.warn` (yellow), `M.redPaint`, `M.water` (opaque),
  `M.waterThin` (see-through), `M.grass`, `M.sand`, `M.rock`, `M.pcb`,
  `M.grille`, `M.slot`, `M.post`; `glossAccent(fam.colour)` and
  `accentMat(fam.colour)` for the family colour; `std({...})` for a
  one-off `MeshStandardMaterial`.

Rules the set keeps, and the checker enforces:

- **Scale.** World units; a 2U server is 8.4 wide, a rack 40 tall, a plant
  60 across. The camera frames the object on its own, so size only has to
  be right relative to the item's parts.
- **Seating.** A link meets the icon at the middle of each side, and walks
  inward from there. Put solid ink at those middles: a thin mast or fin at
  the very edge with air behind it is a `cuts` flag, a part that stops
  short of the middle is a `floats` flag. A ground plate helps the left and
  right sides; a body under the tallest point helps the top.
- **Visibility.** The camera looks down from the front right. Nothing
  hangs unseen under a slab, nothing sits under opaque water: use a narrow
  ceiling strip behind and above, and `M.waterThin`.
- **The badge** goes on a face the camera sees (the front, `+z`, or the
  top with `.rotation.x = -Math.PI / 2`), and is skipped by `badge()` when
  `tex` is null.

## 3. Try it

```text
infragram recipe:try buffer_tank.js --out dist/recipes --arg 4 --family facility --glyph gauge
```

The command stages the shipped scene with the candidate added, renders it,
measures the ink the way the table is measured, and checks where a link
would seat on each side. It writes `buffer_tank.png` (768 px, to look at),
`buffer_tank.svg` (the 192 px icon as it would ship) and
`buffer_tank.report.json`, and prints the verdict:

```text
OK recipe buffer_tank: picture dist/recipes/buffer_tank.png, icon dist/recipes/buffer_tank.svg
  ink: profile [0.19, 0.19, 0.06, 0.12], edge lines on all four sides
  seats: left ok, right ok, top ok
```

Look at the picture every time; a clean report says the geometry seats a
link, not that the thing looks like what was asked. Iterate on the file
until both hold. A page error names the line in the candidate.

## 4. Promote it

```text
infragram recipe:add buffer_tank.js --id buffer-tank --name "Buffer tank" --family facility --arg 4 --alias "thermal store"
```

That writes the builder into `scene.js` and one `item(...)` line into the
item table the set is built from; the flat kit draws a generic stand-in for
a recipe that has no flat drawing of its own. The command then prints the
shipped path, the same as for any change to the set, with the exact commands
to run from the repository root:

1. Render the set with `--install` -- every item re-renders, since the
   scene changed (about fifteen minutes).
2. Generate the node classes -- the class, `IsoBufferTank`.
3. Rebuild the inventory and refresh the ink table.
4. The gates (`verify:quick`, `verify:pictures`, `gen:ink --check`,
   `verify:browser`).

From then on the item is `iso_<family>.IsoBufferTank(...)` in code, a
palette entry in the editor, and a recipe in the editor's 3D builder and in
`Iso(recipe="buffer_tank", ...)`.
