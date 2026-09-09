ATD - Abaqus INP 转 LS-DYNA K（Abaqus/CAE 2020 插件）
=====================================================

版本：1.0.2

安装方法
--------
请复制整个 ATD_Abaqus2020 文件夹，不要只复制其中的 atd 子文件夹。

推荐安装位置：
    %USERPROFILE%\abaqus_plugins\ATD_Abaqus2020\

也可以复制到本机 SIMULIA/Abaqus 2020 已配置的插件目录，例如：
    <SIMULIA 安装目录>\CAE\plugins\2020\ATD_Abaqus2020\

复制完成后，确认目录中存在：
    ATD_Abaqus2020\ATD_plugin.py

然后完全关闭并重新启动 Abaqus/CAE 2020。

使用方法
--------
1. 在 Abaqus/CAE 菜单中选择：Plug-ins > ATD - Abaqus to LS-DYNA
2. 选择 Abaqus .inp 文件和输出 .k 文件。
3. 可选选择 mapping.example.json 或自行编辑的映射 JSON。
4. 建议先勾选严格模式。转换结束后查看生成的：
       <输出文件名>.conversion.json
       <输出文件名>.idmap.csv
5. 报告中 ERROR 必须处理；WARNING 需要结合材料模型、单位制和分析目的复核。

说明
----
- 插件直接读取 INP，不要求当前 Abaqus/CAE 会话已打开模型。
- 转换器不会自动推断单位制；输入数值按原值写入 LS-DYNA 文件。
- mapping.example.json 用于显式覆盖材料、接触、集合或关键字映射。
- 1.0.2 已支持 Abaqus/CAE 写在 *INSTANCE 内的孤立网格；不同实例中重复的
  节点/单元编号会独立解析、重新编号，并按实例/截面生成独立 LS-DYNA Part。
- 无法参数等价转换的 *SECTION CONTROLS 会保留为 K 文件注释并在报告中给出
  WARNING，不会擅自生成可能改变响应的 *HOURGLASS 参数。
- 输出 K 文件用于工程分析前，必须使用对应版本的 LS-DYNA 做关键字检查和算例验证。
