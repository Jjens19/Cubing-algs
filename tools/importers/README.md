# Rebuilding bundled cases

These offline tools maintain `src/data/` and the checked-in SVG diagrams. The
application uses those bundled files directly; it never downloads algorithm
pages on startup. Run commands from the repository root in the project virtual
environment. Download reference pages separately, then pass their local paths.

| Source/task | Command |
| --- | --- |
| SpeedCubeDB COLL, CMLL, SV, LSE (EO4A), or Anti PLL | `python -m tools.importers.speedcubedb COLL --page /tmp/coll.html` |
| CubePal CLL | `python -m tools.importers.cubepal --page /tmp/cll.html --sprite /tmp/c3cll.svg` |
| J Perm WV/OLL/PLL | `python -m tools.importers.jperm --input /tmp/jperm` |
| SpeedCubeDB primary-algorithm cross-reference | `python -m tools.importers.cross_reference --input /tmp/scdb` |
| SpeedCubeDB ELL alternatives | `python -m tools.importers.ell --page /tmp/ell.html` |
| CubingApp EOLR | `python -m tools.importers.eolr --page /tmp/eolr.html` |
| Original ELL diagram regeneration | `python -m tools.importers.ell_svgs` |

Quote the subset argument `"Anti PLL"` when importing it. SV7 deliberately uses
the second listed algorithm. J Perm input files are `wv.js`, `oll.js`, and
`pll.js`; cross-reference input files are `WV.html`, `OLL.html`, and `PLL.html`.
Cross-referencing updates the SVG orientation, so run it after importing J Perm.

Review generated data and run tests before shipping it. Importers write bundled
assets, not the user database. Startup migrations in `src/server.py` apply
bundled changes once and preserve subsequent edits. EOLR is initially imported
into LSE and then moved to its own set by the existing migration.

`common.py` contains shared parsers, state matching, and SVG rendering. Specialized
importers remain where their source format or case-matching rules differ.
