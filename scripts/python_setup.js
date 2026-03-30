const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const projectDir = process.cwd();
const lockFile = path.join(projectDir, 'uv.lock');

function fail(message, error) {
  if (error) {
    console.error(message, error);
  } else {
    console.error(message);
  }
  process.exit(1);
}

function findPythonVersionFile(startDir) {
  let current = startDir;
  while (true) {
    const candidate = path.join(current, '.python-version');
    if (fs.existsSync(candidate)) {
      return candidate;
    }
    const parent = path.dirname(current);
    if (parent === current) {
      return null;
    }
    current = parent;
  }
}

const pythonVersionFile = findPythonVersionFile(projectDir);
if (!pythonVersionFile) {
  fail(`未找到 Python 版本文件: ${projectDir} 及其父目录`);
}

const pythonVersion = fs.readFileSync(pythonVersionFile, 'utf8').trim();
if (!pythonVersion) {
  fail(`Python 版本文件为空: ${pythonVersionFile}`);
}

const args = ['sync', '--python', pythonVersion];
for (let i = 2; i < process.argv.length; i += 1) {
  if (process.argv[i] === '--extra') {
    const extraName = process.argv[i + 1];
    if (!extraName) {
      fail('参数错误: --extra 需要一个名称，例如 --extra dev');
    }
    args.push('--extra', extraName);
    i += 1;
  }
}
// if (fs.existsSync(lockFile)) {
//   args.push('--locked');
// }

// 企业内网多 PyPI 镜像时，首个索引可能没有某包的指定版本；未设置 UV_INDEX_STRATEGY 时默认用 unsafe-best-match
// uv 不使用 pip 的 global.index-url（pip config）；需用 UV_DEFAULT_INDEX / UV_INDEX_URL，或与 pip 对齐导出 PIP_INDEX_URL
const childEnv = { ...process.env };
if (!childEnv.UV_INDEX_STRATEGY) {
  childEnv.UV_INDEX_STRATEGY = 'unsafe-best-match';
}
if (!childEnv.UV_DEFAULT_INDEX && !childEnv.UV_INDEX_URL && process.env.PIP_INDEX_URL) {
  childEnv.UV_DEFAULT_INDEX = process.env.PIP_INDEX_URL;
}

const result = spawnSync('uv', args, {
  cwd: projectDir,
  stdio: 'inherit',
  shell: false,
  env: childEnv,
});

if (result.error) {
  fail('执行 uv 失败，请确认已安装并可在 PATH 中访问 uv。', result.error);
}

if (typeof result.status === 'number' && result.status !== 0) {
  process.exit(result.status);
}
