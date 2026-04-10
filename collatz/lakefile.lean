import Lake
open Lake DSL

package «CollatzBirkhoff» where
  name := "CollatzBirkhoff"

require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @ "master"

lean_lib «CollatzBirkhoff» where
  roots := #[`CollatzBirkhoff]

-- Build order: Defs → Estimates → Spectral → CycleExclusion → Main
lean_lib «CollatzBirkhoff.Defs»          where
lean_lib «CollatzBirkhoff.Estimates»     where
lean_lib «CollatzBirkhoff.Spectral»      where
lean_lib «CollatzBirkhoff.CycleExclusion» where
lean_lib «CollatzBirkhoff.Main»          where
