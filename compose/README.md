# Homelab Compose

My repository for the application that I use docker compose stacks to run "in production"

## Monitoring

My monitoring stack is in my [monitoring repo](https://github.com/Doomlab7/homelab-monitoring)

Glances/Netdata are apart of `monitoring-visibility` which is copied between the 2 hosts due to slightly different docker groups and traefik config

## Networks

`phantomlink` is my homelab network - created with a simple script in ghost/

# Common Patterns

## Traefik Labels

Always use quoted strings for boolean values:

```yaml
labels:
  traefik.enable: "true"        # NOT: true
  traefik.http.routers.foo.rule: Host(`example.com`)
```

## Restart Policy

Use `unless-stopped` for most services:

```yaml
restart: unless-stopped
```

## Timezone

Always set TZ with quotes:

```yaml
environment:
  TZ: "America/Chicago"
```

## Environment Variables

Use `env_file` for service-specific variables:

```yaml
env_file:
  - .env
```

## Network Patterns

### Services that need Traefik routing:
Put on `phantomlink` network so Traefik (host mode) can reach them:

```yaml
networks:
  - phantomlink

networks:
  phantomlink:
    external: true
```

**Never set `hostname:` to a machine name (`ghost`, `babyblue`) on a
`phantomlink` service.** Docker DNS registers the hostname for every container
on the network, so `ghost` silently resolves to that container. syncthing had
`hostname: ghost`, which pointed jellystat at syncthing and grew a 163 GB
error log. Inside the network, address peers by service name
(`http://jellyfin:8096`), not `ghost:<host-port>`.

### Services that need cross-node access:
Use Tailscale sidecar pattern:

```yaml
services:
  myservice:
    depends_on:
      - tailscale
    network_mode: service:tailscale

  tailscale:
    image: tailscale/tailscale:latest
    hostname: myservice-hostname
    environment:
      - TS_STATE_DIR=/var/lib/tailscale
    volumes:
      - /path/to/tailscale/state:/var/lib/tailscale
    devices:
      - /dev/net/tun:/dev/net/tun
    cap_add:
      - net_admin
      - sys_module
    restart: unless-stopped
    privileged: true
    entrypoint: ["tailscaled"]
```

# Docker Compose Project Overview

This project utilizes Docker Compose to manage multiple stacks of applications, running on a couple hosts. The stacks are organized by host, making it easy to identify and manage individual applications.

## Docker Context

I'm using `.envrc` to set the docker context for whichever machine I'm in


## Listing Applications

To list all the applications in the project, you can use the following command:

# TODO

Each application has its own README file located within the corresponding subfolder. These files provide more detailed information about each application, including setup instructions and configuration options.

## Contributing

If you'd like to contribute to this project, please fork the repository and submit a pull request. We welcome all kinds of contributions, including new features, bug fixes, and documentation updates.

# End of Project README
