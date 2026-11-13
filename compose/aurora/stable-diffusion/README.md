# stable-diffusion

AUTOMATIC1111 Stable Diffusion webui + API on the aurora 3090.

- Web UI + API on port 7860
- Models + config live in `/var/docker-storage-zfs/sd` (recovered from crash salvage)
- Source repo (AbdBarho stable-diffusion-webui-docker): `~/projects/personal/stable-diffusion-webui-docker`

## Build the image

```bash
cd ~/projects/personal/stable-diffusion-webui-docker
docker build -t sd-auto:78 ./services/AUTOMATIC1111
```

## GPU prerequisite

Docker needs the NVIDIA runtime registered once (bounces all containers):

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Podman fallback (verified working): `--device nvidia.com/gpu=all --security-opt=label=disable`
