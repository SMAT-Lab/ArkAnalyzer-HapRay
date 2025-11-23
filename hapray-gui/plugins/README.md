# 插件系统说明

## 概述

本系统已从 `tools` 目录改造成 `plugins` 插件系统。每个插件包含描述文件和执行文件，可以独立管理和扩展。

## 插件结构

每个插件只需要包含以下文件：

```
plugins/
  <plugin_id>/
    plugin.json    # 插件描述文件（必需）
```

**注意**：插件系统完全基于描述文件（plugin.json），不需要编写 plugin.py 文件。

## plugin.json 格式

```json
{
  "name": "插件显示名称",
  "description": "插件描述",
  "version": "1.0.0",
  "author": "作者名称",
  "execution": {
    "debug": {
      "cmd": ["可执行文件 node｜python｜exe", "默认脚本2"],
      "script": "相对路径/脚本文件（可选）"
    },
    "release": {
      "cmd": ["可执行文件 node｜python｜exe", "默认脚本2"]
    }
  },
  "parameters": {
    "参数名": {
      "type": "str|int|bool|file|dir|choice",
      "label": "参数显示名称",
      "required": true|false,
      "default": "默认值（可选）",
      "choices": ["选项1", "选项2"],  // choice类型必需
      "help": "参数说明"
    }
  },
  "config": {
    "description": "插件配置项说明",
    "items": {
      "配置项名": {
        "type": "str|int|bool|choice",
        "label": "配置项显示名称",
        "default": "默认值",
        "help": "配置项说明",
        "required": false,
        "choices": ["选项1", "选项2"]  // choice类型必需
      }
    }
  },
  "validation": {
    "custom": true|false  // 是否需要自定义验证
  }
}
```

## 自定义验证规则

如果插件需要自定义验证逻辑，可以在 `plugin.json` 的 `validation` 部分添加规则：

```json
{
  "validation": {
    "custom": true,
    "rules": [
      {
        "type": "file_exists",
        "param": "input_file",
        "message": "输入文件不存在"
      },
      {
        "type": "one_of",
        "params": ["option1", "option2"],
        "message": "必须提供 option1 或 option2 之一"
      },
      {
        "type": "conditional",
        "condition": "mode",
        "required": ["param1", "param2"],
        "message": "当 mode 存在时，param1 和 param2 是必需的"
      }
    ]
  }
}
```

支持的验证规则类型：
- `file_exists`: 检查文件是否存在
- `dir_exists`: 检查目录是否存在
- `one_of`: 至少一个参数必须提供
- `conditional`: 条件验证（如果某个参数存在，则检查其他参数）

## 插件加载

插件系统会自动发现和加载 `plugins` 目录下的所有插件：

1. 扫描 `plugins` 目录下的所有子目录
2. 检查每个目录是否包含 `plugin.json` 和 `plugin.py`
3. 加载插件元数据和类
4. 实例化插件并注册到系统中

## 执行模式

插件支持两种执行模式：

- **debug（调试模式）**：开发和调试模式
  - 使用 `cmd` 配置中的可执行文件（node/python/exe）和脚本路径
  - 可以指定可选的 `script` 脚本文件
  - 适合开发和调试

- **release（发布模式）**：生产环境模式
  - 使用 `cmd` 配置中的可执行文件（node/python/exe）和脚本路径
  - 可以指定可选的 `script` 脚本文件
  - 适合生产环境部署

在 `plugin.json` 中分别配置 `debug` 和 `release` 模式：
```json
{
  "execution": {
    "debug": {
      "cmd": ["python", "scripts/main.py"],
      "script": "scripts/main.py"
    },
    "release": {
      "cmd": ["opt-detector", "opt-detector.exe", "dist/opt-detector/opt-detector.exe"]
    }
  }
}
```

**cmd 格式说明**：
- `cmd` 是一个数组，第一个元素是可执行文件（`node`、`python`、`python3` 或 exe 文件名）
- 第二个元素是脚本路径（可选，主要用于 debug 模式）
- release 模式通常只包含 exe 文件名列表，系统会尝试找到第一个存在的文件

## 配置项

每个插件可以定义自己的配置项，这些配置项用于插件的运行时配置，而不是执行参数。

### 配置项定义

在 `plugin.json` 的 `config` 部分定义配置项：

```json
{
  "config": {
    "description": "插件配置项说明",
    "items": {
      "python_path": {
        "type": "str",
        "label": "Python路径",
        "default": "python",
        "help": "用于执行Python脚本的Python解释器路径",
        "required": false
      },
      "timeout": {
        "type": "int",
        "label": "超时时间（秒）",
        "default": 3600,
        "help": "工具执行的最大超时时间",
        "required": false
      }
    }
  }
}
```

### 配置项类型

- `str`: 字符串类型
- `int`: 整数类型
- `bool`: 布尔类型
- `choice`: 选择类型（需要提供 `choices` 数组）

### 访问配置项

在插件代码中可以通过 `PluginTool` 的方法访问配置：

```python
# 获取单个配置值
python_path = plugin.get_config_value('python_path', 'python')

# 获取所有配置
all_config = plugin.get_all_config()

# 设置配置值
plugin.set_config_value('timeout', 7200)
```

## 配置存储

插件配置存储在用户配置文件中（`~/.hapray-gui/config.json`）：

```json
{
  "plugins": {
    "plugin_id": {
      "path": "插件实际路径",
      "python": "python",  // 或 "node": "node"
      "enabled": true,
      "config": {
        "python_path": "python3",
        "timeout": 3600,
        "log_level": "INFO"
      }
    }
  }
}
```

配置项的值会从 `plugin.json` 中的 `config.items` 定义的默认值初始化，用户可以在设置界面中修改这些值。

## 现有插件

- `perf_testing` - 动态测试插件
- `optimization_detector` - 优化检测插件
- `symbol_recovery` - 符号恢复插件
- `sa` - 静态分析插件

## 添加新插件

1. 在 `plugins` 目录下创建新的插件目录
2. 创建 `plugin.json` 描述文件（包含所有必需信息）
3. 在配置文件中添加插件路径配置
4. 重启应用程序，插件会自动加载

**无需编写任何 Python 代码！** 插件系统会基于 `plugin.json` 自动创建插件实例。

## 兼容性

系统保持向后兼容：
- 旧的 `tools` 目录配置仍然有效
- 配置管理器会优先从 `plugins` 配置读取，然后回退到 `tools` 配置
- 旧的工具类仍然可以工作（通过兼容模式）

