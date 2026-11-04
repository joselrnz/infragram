# Patterns and blueprints

[compose.md](compose.md) is how a diagram is written: frames as `with`
blocks, arrows for wires, no coordinates. Patterns remove repetition inside
that form, and a blueprint is the low-level assembly for generators and
batch exports. Both live in `infragram.patterns` and build on the same
generated classes, so nothing here names an SVG or a provider id by hand.

A pattern is used inside a `with` block by attaching it to the open frame.
Its elements nest once, under that frame, and its parts are wired like any
node:

```python
from infragram.author import Diagram, Edge
from infragram.nodes.aws import compute, databases
from infragram.nodes.frames import aws
from infragram.patterns.aws import Guardrails, MultiAZ

def private_tier(subnet, zone):
    zone.part("web", subnet >> compute.EC2("Web servers", "Auto Scaling"))
    zone.part("db", subnet >> databases.RDS("PostgreSQL", "Multi-AZ"))

with Diagram("Three-tier web"):
    with aws.Cloud("AWS Cloud") as cloud:
        Guardrails().attach(cloud)
        with aws.Region("us-east-1"), aws.VPC("VPC 10.0.0.0/16").row() as vpc:
            zones = MultiAZ(2, private=private_tier).attach(vpc)
    zones.part_for("web", "A") >> Edge("SQL") >> zones.part_for("db", "A")
```

Inside a pattern's `build()` the low-level `parent >> child` form nests, as
the recipe above shows: explicit placement always wins over the `with`
block's adoption, so nothing is drawn twice.

## What a pattern is

A `Pattern` is a named piece of infrastructure that builds once, on first
use, and afterwards answers two questions:

- **Which elements did you make?** `pattern.elements` is the tuple of
  top-level frames or nodes. `pattern.attach(parent)` nests them all under a
  parent.
- **Where is the thing I need to wire?** `pattern.parts` is a read-only
  mapping of stable keys to elements, and `pattern["key"]` reads one. A
  missing key raises with the keys that exist. Keys are the pattern's
  contract; the structure inside is not.

Settings are properties with setters that validate, and they are fixed once
the pattern has built, because changing them afterwards would do nothing.
`repr(pattern)` says whether it has built and how many parts it has.

## The shipped patterns

| Pattern | Draws | Parts |
|---|---|---|
| `aws.Guardrails(name, services)` | Account-wide services as one row in a security zone. Default: GuardDuty, CloudTrail, Security Hub, Config. `services` is a sequence of `(NodeClass, name, detail)`. | one per service, keyed by the slug of its name (`amazon-guardduty`) |
| `aws.Zone(letter, public=, private=)` | One Availability Zone with an optional public subnet and a private one. Each subnet is filled by a callable `(subnet, zone) -> None` that places nodes and registers them with `zone.part(key, element)`. | `public`, `private`, plus whatever the callables register |
| `aws.MultiAZ(count, public=, private=)` | `count` identical zones lettered A, B, C ... from one recipe. | every zone's parts as `key:LETTER`, and `zone:LETTER`; `part_for(key, letter)` and `each(key)` read them |
| `aws.EndpointSubnet(letter, services)` | A private subnet of interface endpoints, each drawn as the service it fronts. | one per service, by slug |
| `hybrid.DirectConnectUplink(site, bandwidth=, asn=)` | A corporate site (datacenter frame with an edge network holding a perimeter firewall and a BGP router), the Direct Connect location with the circuit, and the dashed MACsec/BGP link. | `site`, `edge`, `firewall`, `router`, `location`, `circuit` |

`DirectConnectUplink["site"]` is a frame; add the site's own systems to it.
On the cloud side the circuit terminates on a gateway (a Transit Gateway),
never on an instance.

## Blueprint

A `Blueprint` is the assembly layer beneath `Diagram`: generators and batch
exports use it, an ordinary diagram does not need it. It holds the top-level
elements, the links, and the words the
project document needs, and it validates as it is given things, so a mistake
surfaces at the line that made it:

- `Blueprint(slug, title, description, display="card", theme="light", size="fit")`.
  `slug` must be lower-case words joined by hyphens; `title` and
  `description` must not be empty; `display` is `card` or `icon`; `theme`
  is `light`, `dark` or `darker`. All are properties with setters.
- `Blueprint.fresh(...)` resets the auto-id counters first. Ids are derived
  from names and counted per process, so a script that builds several
  diagrams starts each from zero.
- `plan.add(*elements)` places elements at the top level and returns them;
  a pattern's elements arrive the same way (`plan.add(*pattern.elements)`)
  or nest with `pattern.attach(frame)`.
  `plan.link(source, target, kind=..., label=..., direction=...)` is
  `source.to(target, ...)` that reads as part of the plan.
- `plan.to_project()` is the `CloudProject`, built once and rebuilt only
  after a change. `plan.export(dir, formats=..., display=...)` exports it
  through `compose.export`; `Blueprint.export_many([plans], dir, concurrency=2)`
  exports several at once and requires one theme across them. From the
  command line, a file that ends with `PROJECT = plan` or
  `PROJECTS = [plan_a, plan_b]` is exported by `infragram compose file.py`
  with every export option the command takes.

## Display: cards or icons

Every component draws one of two ways. `card` is the titled box with the icon
in a lane beside the text. `icon` is the bare vendor mark with its caption
beneath and no box, which is how the vendors' own reference architectures
look. The choice is `presentation.display` on the project (`display=` on
`compose.to_project` and on `Blueprint`), a node may override it with its
`editor_display_mode` attribute, and the editor's inspector has a
**Components** row that switches the whole diagram either way. The template
the page downloads remembers the choice.

Exports can draw either look from one document: `--display card|icon` forces
one, and `--display both --write-looks both` writes the cards under the plain
names and the icons as `<slug>-icons.svg` and `<slug>-icons.png`. The page accepts
`?display=icon` in its address to open that way for one visit, which is what
the exporters use.

## Tooltips

Hovering a component in the exported page shows its name, detail, component
id, frame and layer; a wire shows what it joins and its line kind; a frame
shows its kind, its parent and how many components it holds. Every node also
carries an SVG `<title>`, so the exported `.svg` explains itself in any
viewer with no script running.

## Writing a pattern

Subclass `Pattern`, implement `build()`, register parts, and keep settings as
validated properties guarded with `self._guard_unbuilt(name)`:

```python
from infragram.models.topology import TopologyElement
from infragram.nodes.aws import databases
from infragram.nodes.frames import aws
from infragram.patterns import Pattern, PatternError

class ReplicaSet(Pattern):
    def __init__(self, name="Database", replicas=1):
        super().__init__(name)
        self.replicas = replicas

    @property
    def replicas(self): return self._replicas
    @replicas.setter
    def replicas(self, value):
        self._guard_unbuilt("replicas")
        if not 0 <= int(value) <= 5:
            raise PatternError("0 to 5 replicas")
        self._replicas = int(value)

    def build(self) -> TopologyElement:
        group = aws.SecurityGroup(self.name, flow="row")
        primary = self.part("primary", group >> databases.RDS("Primary", "writer"))
        for n in range(self._replicas):
            replica = self.part(f"replica:{n + 1}", group >> databases.RDS(f"Replica {n + 1}", "reader"))
            primary.to(replica, kind="dashed", label="replication")
        return group
```

Determinism rules: build from names, not from randomness or the clock; do
not read the environment; register every element a caller might connect.
Two runs of the same script then produce byte-identical documents, which is
what lets a team review a diagram change as a diff.
