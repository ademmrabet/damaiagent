import { defineConfig } from "@neon/config/v1";

export default defineConfig({
  // Only Object Storage is declared here - Neon's Managed Auth
  // (the `auth: true` the scaffold suggests) isn't used. This app
  // already has its own login system (webapp/auth.py: password +
  // Google/Microsoft OAuth, JWTs) - see docs/decisions.md, 2026-09-20.
  buckets: {
    // Private (presigned URLs only, never a public link) - matches
    // NEON_BUCKET_NAME's default in webapp/storage.py, so no extra
    // env var is needed to point the app at this bucket.
    uploads: { access: "private" },
  },
  // Branch policy: per-branch tuning (left at the scaffolded default -
  // this project doesn't use branches yet, but auto-expiring a
  // non-default branch's bucket after 7 days is a sensible default
  // rather than something worth overriding now).
  branch: (branch) => {
    if (branch.isDefault) {
      return {};
    }
    if (!branch.exists) {
      return { ttl: "7d" };
    }
    return {};
  },
});
