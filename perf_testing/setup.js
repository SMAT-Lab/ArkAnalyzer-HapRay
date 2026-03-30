const path = require('path');
const { spawnSync } = require('child_process');

const projectDir = process.cwd();

// 与 ../scripts/python_setup.js 一致：uv 不读 pip config，可与 pip 对齐使用 PIP_INDEX_URL 或 UV_DEFAULT_INDEX
if (!process.env.UV_DEFAULT_INDEX && !process.env.UV_INDEX_URL && process.env.PIP_INDEX_URL) {
  process.env.UV_DEFAULT_INDEX = process.env.PIP_INDEX_URL;
}

function fail(message, error) {
  if (error) {
    console.error(message, error);
  } else {
    console.error(message);
  }
  process.exit(1);
}

function run(command, args, cwd = projectDir) {
  const result = spawnSync(command, args, {
    cwd,
    stdio: 'inherit',
    shell: false,
  });
  if (result.error) {
    fail(`执行命令失败: ${command}`, result.error);
  }
  if (typeof result.status === 'number' && result.status !== 0) {
    process.exit(result.status);
  }
}

// phone-agent 由 pyproject 依赖安装；对当前 venv 内 site-packages 的 device.py 打 swipe 补丁（路径由 Python 解析，跨 OS）
run('uv', ['run', 'python', path.join(projectDir, 'scripts', 'patch_phone_agent_device.py')]);
