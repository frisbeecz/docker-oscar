# OSCAR Helm chart

<!-- SPDX-License-Identifier: Apache-2.0 -->

Chart `0.1.2` runs OSCAR `2.1.1` using Selkies, not VNC. It has no chart
dependencies, controllers, CRDs, RBAC or migration hooks. This is a new
installation chart, **not an upgrade path for an old OSCAR release**.

```sh
helm install demo charts/oscar --namespace oscar --create-namespace -f values.yaml
```

Defaults: one Deployment replica, `Recreate`, ClusterIP HTTP Service on named
port `http`/3000, three persistent generation-v2 claims, both routes disabled.
An available default StorageClass (or suitable pre-provisioned volumes) is
needed. There is no ephemeral fallback when storage is unavailable.

For local access, forward the Service only to loopback:

```sh
kubectl --context YOUR_EXPLICIT_CONTEXT -n oscar port-forward service/demo-oscar 3000:3000 --address 127.0.0.1
```

Use `http://127.0.0.1:3000` as a browser-supported local secure context.
For remote use, **HTTPS and authentication are operator requirements**.
The chart is not an identity provider and has no default password.

## Values and security

| Values | Default / contract |
| --- | --- |
| `nameOverride`, `fullnameOverride` | Empty; DNS labels, at most 63 characters |
| `replicaCount` | Exactly `1`; no concurrent writers/rolling update |
| `image.repository`, `tag` | `ghcr.io/frisbeecz/docker-oscar`, `2.1.1-r3` |
| `image.digest` | Empty or `sha256:<64 hex>`; takes precedence over tag |
| `image.pullPolicy`, `imagePullSecrets` | `IfNotPresent`, `[]` (existing Secret names) |
| `serviceAccount.create`, `name` | `true`, empty (generated); `false` + empty selects `default` |
| `env` | String map; `PUID=1000`, `PGID=1000`, `TZ=Etc/UTC` |
| `envFrom` | `[]`; existing `secretRef` or `configMapRef`, optional prefix |
| `resources.requests` | CPU `250m`, memory `512Mi` |
| `resources.limits` | CPU `2`, memory `2Gi` |
| `nodeSelector`, `tolerations`, `affinity` | `{}`, `[]`, `{}` |
| `startupProbe` | TCP `http`, period/timeout/failureThreshold `5/3/60` |
| `readinessProbe` | TCP `http`, `10/3/3` |
| `livenessProbe` | TCP `http`, `30/3/3` |
| `extraPvcMounts` | `[]`; only PVC references under `/imports/<safe-subdirectory>` |

Base init may run as root to set up the configured nonzero UID/GID. The app
runs unprivileged; this chart does **not** claim Pod Security Restricted or
`runAsNonRoot` compatibility. Both pod and ServiceAccount disable token
automount. There is no privileged mode, hostNetwork, hostPath, socket mount or
capability-add option. `allowPrivilegeEscalation` is false; `NET_RAW` is
dropped, matching the image runtime harness. Remaining base/init capability
requirements need environment-specific confirmation; startup smoke checks the
native container only, not Kubernetes compatibility. Static rendering is not
that proof.

`PIXELFLUX_WAYLAND`, `RESTART_APP` and `HARDEN_DESKTOP` remain string `"true"`.
Passwordless sudo/desktop command hardening comes from the pinned image.
Do not use arbitrary environment configuration to re-enable unsafe base
features. Values and cluster credentials are trusted administrative inputs,
not an OS sandbox.

Use existing Secrets, never passwords in checked-in values:

```yaml
envFrom:
  - secretRef:
      name: desktop-auth
```

The Secret's supported keys and any proxy authentication must be configured
for the actual pinned Selkies/proxy versions; this example does not create a
Secret or invent a universal auth variable.

For immutable image selection:

```yaml
image:
  repository: ghcr.io/frisbeecz/docker-oscar
  # Replace with the digest of an actually verified release manifest.
  digest: "sha256:REPLACE_WITH_VERIFIED_64_HEX_DIGEST"
```

The placeholder is deliberately not installable. Do not treat an example
digest or tag as evidence that an image has been published or tested.

Probes accept Kubernetes probe objects. When changing handler type, remove
the merged default TCP handler explicitly:

```yaml
readinessProbe:
  tcpSocket: null
  httpGet:
    path: /
    port: http
  periodSeconds: 10
```

Resources, scheduling and probes still need Kubernetes admission validation
in the target environment. Chart JSON Schema and pinned strict resource
schemas cannot evaluate every admission rule or Gateway CEL expression.

## Storage, backup and uninstall

| Role | Default size | Mount | Default access |
| --- | --- | --- | --- |
| config | `1Gi` | `/config` | Read/write |
| data | `5Gi` | `/config/Documents/OSCAR20_Data` | Read/write |
| sdcard | `2Gi` | `/config/SDCARD` | Read-only |

All default to `accessModes: [ReadWriteOnce]`, `storageClass: null`,
`existingClaim: ""`. Each role requires persistent storage; there is no
`enabled: false` switch. `/dev/shm` alone is an in-memory `emptyDir` limited
to `512Mi`; it is not application storage.

For **each** role, `storageClass: null`/omitted emits no `storageClassName`
(cluster default); `storageClass: ""` emits an explicit empty string
(no default class); a named string selects that class. These states are not
interchangeable. Dynamic provisioning may not work with an empty class.
An `existingClaim` is used exactly as supplied in the release namespace;
size/accessModes/storageClass then do not modify that external claim.
`persistence.sdcard.readOnly: false` is the explicit writable-input opt-in.

Names are `<fullname>-config-v2`, `-data-v2`, `-sdcard-v2`. The fullname is
truncated **before** the role suffix, preserving distinct stable names within
63 characters even for long release/override names. Changing a release name
or override changes claim names: do not do this accidentally during upgrades.

**Back up config, data and SD separately.** The data and SD volumes are nested
mounts under `/config`; a config PVC snapshot does not include their content.
Stop application writes for a consistent backup, follow the storage provider's
snapshot/export procedure, and test restore to separate claims. The chart
does not copy, import, convert or migrate any old profiles.

Managed PVCs carry `helm.sh/resource-policy: keep`. A Helm uninstall leaves
them **orphaned**, still with their original UID and Helm ownership metadata.
This is not a backup, nor automatic Helm re-adoption. Namespace deletion,
manual PVC deletion or the storage provider's reclaim policy may still destroy
data. Keep/reclaim behavior must be tested with your actual Helm/storage stack.

To reuse retained claims safely, supply all names explicitly in a *new*
release (example for claims originally created by `demo`):

```yaml
persistence:
  config:
    existingClaim: demo-oscar-config-v2
  data:
    existingClaim: demo-oscar-data-v2
  sdcard:
    existingClaim: demo-oscar-sdcard-v2
```

```sh
helm install restored charts/oscar -n oscar -f retained-claims.yaml
```

The chart emits no PVC for an external claim, does not change its owner
labels/annotations and does not delete it on the second release's uninstall.
Do **not** remove ownership metadata or use ownership-taking flags to force
adoption. Do not reinstall over orphan names assuming Helm will manage them
again. Never point two running OSCAR releases at the same data claims.

For a one-off import, use only an isolated working copy:

```yaml
extraPvcMounts:
  - name: legacy
    claimName: legacy-working-copy
    mountPath: /imports/legacy
    # Defaults to true when omitted.
    readOnly: true
```

Only `name`, `claimName`, `mountPath`, `readOnly` are accepted. Names and paths
must be unique; `config`, `data`, `sdcard`, `shm` are reserved names. Paths
contain a single alphanumeric/underscore/hyphen subdirectory under `/imports`,
without `..`, slashes or application-mount overlap. No generic volume/hostPath
escape exists. If an importer needs write access, explicitly enable it only
on another disposable copy, never the original.

## Ingress and Gateway API

Both routes are independent and disabled by default. They target the same
Service port: Ingress by name `http`, HTTPRoute by number `3000` (Gateway API
backendRefs require a numeric port). No controller, Gateway, certificate,
Secret, cert-manager or CRD is created.

Ingress-only example:

```yaml
ingress:
  enabled: true
  className: example
  annotations: {}
  hosts:
    - host: oscar.example.org
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: oscar-tls
      hosts: [oscar.example.org]
```

Gateway-only example (requires an existing HTTPS listener/Gateway):

```yaml
gateway:
  enabled: true
  parentRefs:
    - name: shared
      namespace: gateways
      sectionName: https
  hostnames: [oscar.example.org]
  path: /
```

The Gateway must permit routes from the release namespace. TLS terminates on
that Gateway. Enabling HTTPRoute requires discovery of the exact
`gateway.networking.k8s.io/v1/HTTPRoute` resource, otherwise rendering/install
fails with an explanation. When disabled there is no Gateway API dependency.
Offline positive renders must explicitly pass:

```sh
helm template demo charts/oscar -f gateway-values.yaml \
  --api-versions gateway.networking.k8s.io/v1/HTTPRoute
```

Both snippets can be combined. Disabling one route does not reconfigure the
other. Prefer root `/`; arbitrary URL prefix rewriting is not promised.
The client needs HTTPS/WebCodecs, WebSocket upgrades, and controller-specific
long-lived connection/read/write timeouts. Configure authentication and
TLS/certificate policy on the actual proxy/controller. There is no portable
annotation that implements these for every controller.

Default Selkies streaming is WebSocket/WebCodecs; no UDP, STUN, TURN or
WebRTC infrastructure is required by this chart. Optional Selkies WebRTC
configuration is a separate integration, not this acceptance gate.

## Validation scope (not Kubernetes deployment acceptance)

```sh
python3 -m pytest
python3 -m ci.chart --helm helm --out-dir artifacts/chart/helm-4.3.2
```

The default suite contains image and chart static/contract tests, **not**
native runtime tests. `ci.chart` runs real pytest, `helm lint --strict`, all
four route renders, existing claims, digest, empty storage class and extra
PVC cases, then real kubeconform `0.8.0 -strict`. Helm lint has no
`--api-versions` and its lint mode only logs template `fail()` as informational;
positive/negative `helm template` tests enforce the capability check.

Every resource is mapped by exact kind/API to a local pinned schema, without
default registry fallback or `-ignore-missing-schemas`. Kubernetes `1.37.0`
standalone-strict files and upstream Gateway `1.7.0` CRDs/derived HTTPRoute
schema are verified against `ci/tools.lock.json`. Existing successful inputs
are reused and checksum-verified; a corrupt cache fails instead of downloading
over it. Kubernetes schema dialect declarations remain byte-for-byte pinned;
kubeconform handles their generic meta-schema URI. The HTTPRoute derivation
uses the shared strict schema helper, not permissive unknown-field handling.

Receipts identify commit, canonical dirty state (including nonignored
untracked files), command, cwd, exit, platform and explicit checks. Existing
receipts are never overwritten. Local supported tool versions are checked;
Linux tool archive checksum installation and the Helm `3.19.0`/`4.3.2` CI
matrix remain mandatory. Rendering is **not deployment PASS**.

On 2026-11-15 the user explicitly approved startup-only native smoke, superseding
the historical plan's mandatory GUI/profile/persistence/kind acceptance. Normal
CI/release does not provision, install into or tear down Kubernetes. The retained
`ci.kubernetes`/`ci.gui` helpers and their unit tests are historical, non-gating
utilities; they are not evidence of a successful native deployment.

Current `startup-smoke-v1` checks only container-running state, loopback HTTP200
and the same unprivileged OSCAR process for at least 10 seconds on both native
architectures. Remote GUI usability/media, import, profile/data persistence,
watchdog recovery, actual Kubernetes install/storage retention/routing and
TLS/authentication remain **unverified**. Storage/backup/migration cautions above
still apply. See [acceptance](acceptance.md) for current evidence and
[releasing](releasing.md) for unchanged source-distribution obligations.
