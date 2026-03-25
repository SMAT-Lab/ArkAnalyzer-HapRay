const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const projectDir = process.cwd();
const thirdPartyDir = path.resolve(projectDir, '../third-party');
const openAutoGlmDir = path.join(thirdPartyDir, 'Open-AutoGLM');
const patchFile = path.resolve(projectDir, '../Open-AutoGLM-swipe.diff');

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

if (!fs.existsSync(openAutoGlmDir)) {
  run('git', ['clone', 'https://gitcode.com/zai-org/Open-AutoGLM.git', openAutoGlmDir]);
  if (fs.existsSync(patchFile)) {
    run('git', ['apply', patchFile], openAutoGlmDir);
  }
}

const pythonPath =
  process.platform === 'win32' ? '.\\.venv\\Scripts\\python.exe' : './.venv/bin/python';

run('uv', ['pip', 'install', '--python', pythonPath, '-r', path.join(openAutoGlmDir, 'requirements.txt')]);
run('uv', ['pip', 'install', '--python', pythonPath, openAutoGlmDir]);
