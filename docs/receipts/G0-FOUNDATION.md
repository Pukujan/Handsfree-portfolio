# G0 Foundation Verification Receipt

**Gate:** #2
**Status:** PASS
**Verification branch:** `g0-verification`
**Verified head before receipt update:** `e37c63ca83ba4c18911d18c9e554d5ea6c4fdfd7`
**GitHub Actions run:** `32295292427`
**Job:** `foundation` / `96205079101`

## Acceptance targets

- React/Vite web builds against a deterministic fake conversation adapter — **PASS**.
- Theme system remains presentation-only — **PASS** via web test + architecture boundary.
- FastAPI delivery composes pure application/domain code through inward-owned ports — **PASS**.
- Application/property tests prove public-pack authority and fail-closed grounding — **PASS**.
- JSON contracts validate against Draft 2020-12 schemas and representative fixtures — **PASS**.
- Architecture guard rejects forbidden framework/provider dependency direction — **PASS**.

## Observed CI steps

1. Install web dependencies — PASS
2. Build web — PASS
3. Test web — PASS
4. Install API development dependencies — PASS
5. Architecture boundaries — PASS
6. Contract validation — PASS
7. API tests — PASS

## Notes

Two bootstrap defects were caught and fixed before PASS:
- invalid non-semver `packageManager` declaration for pnpm;
- missing Vite client type declaration for CSS side-effect imports.

This receipt records observed CI evidence. G0 may close after this receipt head itself re-runs green.
