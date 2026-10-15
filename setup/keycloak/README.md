# Keycloak single sign-on (development)

Root the Box can authenticate players through any OpenID Connect provider
(`auth = "oidc"`). This folder holds a ready-made **development** Keycloak
realm for trying it out locally.

> `rootthebox-realm.json` contains a fixed client secret and test passwords.
> Never import it into a production Keycloak.

## 1. Import the realm

With Keycloak running on `http://localhost:8080`:

1. Open the admin console at `http://localhost:8080/admin` and sign in.
2. Open the realm dropdown (top left) and choose **Create realm**.
3. **Browse** to `setup/keycloak/rootthebox-realm.json`, then click **Create**.

This creates:

| Item | Value |
|---|---|
| Realm | `rootthebox` |
| Client | `rootthebox` (confidential, PKCE S256), secret `rtb-dev-secret-DO-NOT-USE-IN-PRODUCTION` |
| Redirect URI | `http://localhost:8888/oidc/callback` |
| Admin role | `rtb-admin` (realm role, sent in the ID token as `roles`) |
| Users | `player1` / `player1`, `player2` / `player2`, `rtbadmin` / `rtbadmin` (has `rtb-admin`) |

To check the import, open
`http://localhost:8080/realms/rootthebox/.well-known/openid-configuration`.
Its `issuer` should be `http://localhost:8080/realms/rootthebox`.

## 2. Point Root the Box at it

Set these options in `files/rootthebox.cfg`, or as upper-case environment
variables (e.g. in `docker-compose.dev.yml`):

```
AUTH=oidc
OIDC_ISSUER=http://localhost:8080/realms/rootthebox
OIDC_BACKCHANNEL_URL=http://host.docker.internal:8080/realms/rootthebox
OIDC_CLIENT_ID=rootthebox
OIDC_CLIENT_SECRET=rtb-dev-secret-DO-NOT-USE-IN-PRODUCTION
OIDC_REDIRECT_URL=http://localhost:8888/oidc/callback
```

Optional settings:

| Option | Default | Meaning |
|---|---|---|
| `oidc_scopes` | `openid profile email` | Scopes requested at login |
| `oidc_roles_claim` | `roles` | ID token claim with the user's roles; dotted paths such as `realm_access.roles` also work |
| `oidc_admin_role` | `rtb-admin` | Role that grants admin rights in Root the Box |
| `oidc_logout` | `True` | Also end the Keycloak session when a user logs out of Root the Box |

### Why two URLs?

Your browser reaches Keycloak at `localhost:8080`. Inside the Root the Box
container, `localhost` is the container itself, so the server uses
`OIDC_BACKCHANNEL_URL` (`host.docker.internal`) for its own requests:
discovery, token exchange and signing keys.

Keycloak normally builds the token issuer (`iss`) from whichever host it was
called on. The dev realm sets its **Frontend URL** to `http://localhost:8080`
so the issuer always matches `OIDC_ISSUER`.

In production, Keycloak is usually reachable at one public hostname
(`KC_HOSTNAME`). There you can leave `OIDC_BACKCHANNEL_URL` empty.

## How sign-in works

| Who | What happens |
|---|---|
| **New users** | Sent to Keycloak, then to `/onboarding` to choose a handle and a team (join with a team code, or create one if public teams are on). Admins (`rtb-admin`) only choose a handle. |
| **Returning users** | Go straight to their dashboard. Name, email and admin rights are refreshed from Keycloak on every login. |
| **Players with no team** (for example, removed from one) | Asked to pick a team again on their next login. |

Accounts are linked by Keycloak's stable subject id (`sub`), never by email.
Password login, registration and password reset are disabled in this mode.
Admin accounts come from Keycloak, so no local `admin` user is created.
