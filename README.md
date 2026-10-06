# CFD Agent Harness MVP

面向工程人员的固定冷热混合三通弯管Harness。GLM解析需求，CadQuery生成流体域，Fluent Meshing生成网格，PyFluent配置和运行求解，Python规则执行分阶段工程校验。

**目标环境：Windows 11 + 本地 Fluent 2024 R2。当前实现为首版，需要在目标Fluent上完成集成验证。云端未运行真实Fluent或GLM请求，不能宣称完整CFD链路已验证。**

## 安装（本地PowerShell）

需要Python 3.11或3.12、已安装且可正常手动启动的Fluent 2024 R2及可用许可证。安装PyFluent不等于安装Fluent。

```powershell
cd C:\path\to\cfd-agent-mvp
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
$env:FLUENT_EXECUTABLE = 'C:\Program Files\ANSYS Inc\v242\fluent\ntbin\win64\fluent.exe'
.\.venv\Scripts\cfd-agent.exe doctor
.\.venv\Scripts\cfd-agent.exe doctor --launch
.\.venv\Scripts\python.exe -m pytest -q
```

调整Fluent路径为实际安装位置。许可证可以通过已有ANSYS许可配置获取，不一定需要环境变量；doctor只检查存在性，真实启动才验证许可。

## 先验证几何与规则

```powershell
.\.venv\Scripts\cfd-agent.exe run examples\mixing_tee.yaml --geometry-only
```

用户输入使用SI单位，STEP文件使用mm并记录单位；Solver导入后自动回查并核验SI尺寸。

生成真实STEP、几何摘要、前置规则记录和报告；网格及求解明确标记未执行。几何为单一连通流体实体，左侧冷水入口、下方热水入口、上方混合出口。长度单位m、温度K、速度m/s。`junction_angle`是支管接入弯头中心线位置的参数，不是支管倾角；支管始终竖直。

## 在本地Fluent执行

```powershell
.\.venv\Scripts\cfd-agent.exe run examples\mixing_tee.yaml
```

启动2024 R2 Meshing，执行Watertight Geometry工作流，再启动Solver。所有网格由Fluent Meshing生成。可用`--rules configs/validation.yaml`覆盖集中判据。API不兼容、STEP边界名丢失、质量证据缺失或门禁阻断时，保留日志并停止，退出码非零。

`max_runtime_seconds`在求解批次之间检查，不是对阻塞Fluent调用的硬超时；Fluent启动超时为120秒。

**待本地验证的关键点**：CAD导入是否保留STEP面名、工作流任务参数、质量日志格式、报告定义类型及返回结构。当前不猜测边界、不补造质量值、不跳过门禁。若失败，请提供运行目录中的`report.md`和相关Fluent日志以定位；先检查日志中是否包含敏感项目信息。

## GLM自然语言解析

在本地安全配置`GLM_API_KEY`或`ZHIPU_API_KEY`，不要把密钥提交到Git。请求发往智谱官方HTTPS接口`open.bigmodel.cn`。默认模型`glm-4-flash`，可用`--model`指定账号可访问的GLM模型。

```powershell
.\.venv\Scripts\cfd-agent.exe parse examples\request.txt --output parsed-spec.json
.\.venv\Scripts\cfd-agent.exe run parsed-spec.json
```

缺少必填值时返回中文补充问题，退出码2；用户完善需求后重新解析。JSON/YAML入口不依赖GLM密钥。GLM输出经过Schema校验，不执行模型生成代码。示例物性只是室温演示值，未伪装成手册溯源值。

## 瞬态

在工况中设置`controls.mode: transient`、`time_step`、`time_steps`和`iterations_per_step`。名义库朗数仅为预筛查；瞬态每步残差及观察窗口的工程充分性需单独验证，当前报告不会把稳态监测稳定判据用于瞬态。每步残差缺失或不达标会使结果无法通过验证。

## 产物与状态

每次运行使用独立`runs/<UTC时间>-<随机ID>/`，保存输入、版本、STEP、网格、case/data、日志、结果JSON及Markdown报告。退出码0表示对应命令完成，不表示达到产品验收条件；`geometry_only_complete`只验证几何。

八个校验点：需求、几何、网格、物理/物性/时间步、实际算例设置、运行过程、求解结果、报告完整性。状态包括PASS、WARNING、BLOCKER、UNVERIFIED。前置BLOCKER和UNVERIFIED阻止求解；结果证据不足返回`results_not_validated`和非零退出码。

本版不含GUI、自动优化、网格独立性研究、实验验证、自动恢复和分布式执行。无网格独立性与实验对照的结果仅用于初步分析，不能单独用于产品验收。

## 开发

```bash
python -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest -q
.venv/bin/cfd-agent run examples/mixing_tee.yaml --geometry-only
```

详见`docs/architecture.md`、`docs/engineering_limits.md`和`docs/local_validation.md`。
