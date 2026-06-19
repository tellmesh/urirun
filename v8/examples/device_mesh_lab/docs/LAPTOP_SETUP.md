# Laptop and desktop setup

This is the minimal setup for orchestration between two real computers on the
same LAN.

## 1. Install the code on both machines

On the desktop/controller and on the laptop:

```bash
git clone https://github.com/tellmesh/urihandler.git
cd urihandler/v8/examples/device_mesh_lab
python3 -m venv .venv
. .venv/bin/activate
pip install -e ../../../adapters/python
pip install litellm
```

`litellm` is required only on the controller. The device agent itself uses the
Python standard library.

## 2. Choose addresses

Find IP addresses:

```bash
ip addr show
```

Example:

```txt
desktop: 192.168.1.10
laptop:  192.168.1.22
```

Use one shared token if the machines are on a network you do not fully trust:

```bash
export URIRUN_MESH_SHARED_TOKEN='change-me'
```

## 3. Start the laptop agent

On the laptop:

```bash
cd urihandler/v8/examples/device_mesh_lab
. .venv/bin/activate
URIRUN_MESH_DEVICE_NAME=laptop \
URIRUN_MESH_DEVICE_ROLE=remote-laptop \
URIRUN_MESH_AGENT_HOST=0.0.0.0 \
URIRUN_MESH_AGENT_PORT=18765 \
URIRUN_MESH_SHARED_TOKEN="$URIRUN_MESH_SHARED_TOKEN" \
make agent
```

Test from the desktop:

```bash
curl -H "Authorization: Bearer $URIRUN_MESH_SHARED_TOKEN" \
  http://192.168.1.22:18765/routes
```

If this fails, check firewall rules:

```bash
sudo ufw allow 18765/tcp
```

## 4. Start the desktop agent

On the desktop/controller:

```bash
cd urihandler/v8/examples/device_mesh_lab
. .venv/bin/activate
URIRUN_MESH_DEVICE_NAME=desktop \
URIRUN_MESH_DEVICE_ROLE=controller \
URIRUN_MESH_AGENT_HOST=0.0.0.0 \
URIRUN_MESH_AGENT_PORT=18765 \
URIRUN_MESH_SHARED_TOKEN="$URIRUN_MESH_SHARED_TOKEN" \
make agent
```

## 5. Start the dashboard/controller

On the desktop/controller, in another terminal:

```bash
cd urihandler/v8/examples/device_mesh_lab
. .venv/bin/activate
export URIRUN_MESH_PEERS='desktop=http://192.168.1.10:18765,laptop=http://192.168.1.22:18765'
export URIRUN_MESH_DASHBOARD_HOST=0.0.0.0
export URIRUN_MESH_DASHBOARD_PORT=8193
export URIRUN_MESH_SHARED_TOKEN="$URIRUN_MESH_SHARED_TOKEN"
make dashboard
```

Open:

```txt
http://192.168.1.10:8193/
```

## 6. Configure LLM

Put model/provider values in `/home/tom/github/tellmesh/urihandler/.env` on the
controller:

```env
LLM_MODEL=openrouter/your-model
OPENROUTER_API_KEY=...
```

The controller reads this file. Agents do not need LLM keys.

## 7. Run a prompt

Use the dashboard prompt, for example:

```txt
Sprawdź desktop i laptop, pokaż procesy, sprawdź czy jest python3 i zapisz notatkę na desktopie.
```

The controller will:

1. discover `/routes` on both machines,
2. compile a `urirun.v8` registry,
3. ask LiteLLM for a URI flow,
4. reject any URI not present in the registry,
5. run the flow by calling each device's `/run`.

## 8. Add stronger automation later

For GUI automation, do not expose a generic shell endpoint. Add a specific
adapter and route, for example:

```txt
kvm://laptop/monitor/primary/query/screenshot
him://laptop/keyboard/command/type-text
ocr://laptop/image/latest/query/text
browser://laptop/page/command/click
```

Once the laptop agent advertises those routes in `/routes`, the controller and
LLM can use them in the same flow format.
