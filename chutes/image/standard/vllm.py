from chutes.image import Image

VLLM = "parachutes/vllm:0.6.3"

# To build this yourself, you can use something like:
# image = (
#     Image("vllm", "0.6.3")
#     .with_python("3.12.7")
#     .apt_install(["google-perftools", "git"])
#     .run_command("useradd vllm -s /sbin/nologin")
#     .run_command("mkdir -p /workspace && chown vllm:vllm /workspace")
#     .set_user("vllm")
#     .set_workdir("/workspace")
#     .with_env("PATH", "/opt/python/bin:$PATH")
#     .run_command("/opt/python/bin/pip install --no-cache vllm==0.6.3 wheel packaging")
#     .run_command("/opt/python/bin/pip install --no-cache flash-attn==2.6.3")
#     .run_command("/opt/python/bin/pip install --no-cache git+https://github.com/jondurbin/chutes")
#     .run_command("/opt/python/bin/pip uninstall -y xformers")
# )