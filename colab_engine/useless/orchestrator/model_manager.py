import asyncio
import subprocess
import os
import time
import logging
import aiohttp
import config

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, llama_server_bin: str, model_dir: str, listen_host: str, backend_port: int):
        self.llama_server_bin = llama_server_bin
        self.model_dir = model_dir
        self.listen_host = listen_host
        self.backend_port = backend_port
        
        self.current_model = None
        self.process = None
        self.lock = asyncio.Lock()
        
    async def get_vram_usage(self) -> int:
        """Returns VRAM usage in MB via nvidia-smi."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            return int(stdout.decode().strip().split()[0])
        except Exception as e:
            logger.error(f"Failed to read VRAM usage: {e}")
            return 99999

    async def kill_current_model(self):
        if not self.process:
            return

        logger.info(f"Sending SIGTERM to llama-server (PID: {self.process.pid})")
        try:
            self.process.terminate()
            await asyncio.wait_for(self.process.wait(), timeout=10.0)
        except ProcessLookupError:
            logger.info("Process already terminated.")
        except asyncio.TimeoutError:
            logger.warning("llama-server did not terminate, sending SIGKILL")
            self.process.kill()
            await self.process.wait()
            
        self.process = None
        self.current_model = None
        
        # Verify VRAM release
        start_time = time.time()
        vram = 99999
        while time.time() - start_time < config.VRAM_RELEASE_VERIFY_TIMEOUT_S:
            vram = await self.get_vram_usage()
            if vram < config.VRAM_RELEASE_THRESHOLD_MB:
                logger.info(f"VRAM released successfully (Current: {vram} MB)")
                return
            await asyncio.sleep(1.0)
            
        logger.error(f"CRITICAL: VRAM not fully released after kill (Current: {vram} MB). Trying emergency GC.")
        import gc; gc.collect()
        
    async def ensure_model(self, model_key: str):
        async with self.lock:
            # Resolve alias
            target_model_key = None
            for key, md in config.MODELS.items():
                if model_key in md["aliases"] or model_key == key:
                    target_model_key = key
                    break
            
            if not target_model_key:
                logger.warning(f"Model '{model_key}' not found, falling back to deephat")
                target_model_key = "deephat"

            if self.current_model == target_model_key and self.process is not None:
                return # Already loaded
                
            logger.info(f"Swapping model to {target_model_key}")
            await self.kill_current_model()
            
            md = config.MODELS[target_model_key]
            
            cmd = [self.llama_server_bin]
            cmd.extend(["-m", os.path.join(self.model_dir, md["file"])])
            
            if md["mmproj"]:
                cmd.extend(["--mmproj", os.path.join(self.model_dir, md["mmproj"])])
                
            cmd.extend(config.COMMON_FLAGS)
            cmd.extend(["--host", self.listen_host, "--port", str(self.backend_port)])
            cmd.extend(md["extra_flags"])
            
            logger.info(f"Launching llama-server: {' '.join(cmd)}")
            
            # Pipe to log file instead of DEVNULL so we can see why it crashes in Colab
            log_file = open('/var/log/llama-server.log', 'w') if os.path.exists('/var/log') else open('llama-server.log', 'w')
            
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=log_file,
                stderr=log_file
            )
            self.current_model = target_model_key
            
            # Poll health
            health_url = f"http://{self.listen_host}:{self.backend_port}/health"
            retries = 0
            async with aiohttp.ClientSession() as session:
                while retries < config.HEALTH_POLL_MAX_RETRIES:
                    try:
                        async with session.get(health_url, timeout=aiohttp.ClientTimeout(total=1.0)) as resp:
                            if resp.status == 200:
                                logger.info(f"Model {target_model_key} loaded and healthy.")
                                return
                    except Exception:
                        pass
                retries += 1
                await asyncio.sleep(config.HEALTH_POLL_INTERVAL_S)
                
            logger.error("Failed to load model within timeout.")
            await self.kill_current_model()
            raise RuntimeError(f"Failed to load model {target_model_key}")
