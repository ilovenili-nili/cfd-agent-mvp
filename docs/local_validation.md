# Windows 11 / Fluent 2024 R2 本地集成验证

本文件描述待执行的真实验证，不代表已经通过。

1. 使用README安装命令，手动确认Fluent 2024 R2可以取得许可证启动。
2. 执行doctor、单元测试及geometry-only。检查STEP是单一连通流体域和三个端口。
3. 执行完整run。先验证Meshing导入边界名称：cold_inlet、hot_inlet、mixed_outlet。CAD导入面名未保留则需要对2024 R2的边界识别接口做实际适配，禁止猜测编号。
4. 检查面网格、近壁层和体网格任务的日志与mesh/metrics.json。指标缺失时保持门禁阻断并定位日志格式。
5. 检查case/settings.json中的实际配置、能量模型、水、入口及出口、SST和操作压力。
6. 检查cas.h5/data文件，确认执行了预期迭代数、报告定义正常采样，残差字段覆盖全部方程。
7. 评估质量/能量守恒、出口温度、压力及速度，确认非物理工况会被拦截。
8. 再运行带time_step的瞬态工况，核对每步历史；观察窗口和时间敏感性不应由固定常数自动认证。

当前云端验证：真实CAD生成与STEP回读、输入模型、规则门禁、日志解析和geometry-only报告。真实Fluent和GLM请求未执行。
