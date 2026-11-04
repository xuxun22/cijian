# gotcha：wx.uploadFile 无法自定义 multipart 文件名 → orig_name 变 tmp_xxx

> 2026-11-04 · 仓库：cijian-mp / cijian-api · 类别：gotcha · 状态：现行（已修复）

## 症状

小程序选相册图片或聊天文件上传，任务列表/任务详情显示 `tmp_xxx` 而不是原始文件名
（或期望的友好名）。网页端上传不受影响。

## 根因

`wx.uploadFile` 的 `UploadFileOption` **没有 `fileName` 参数**（别和 `wx.shareFileMessage`
的 fileName 混淆——那个有）。multipart 里 Content-Disposition 的文件名只能取 `filePath`
的尾段，而 `wx.chooseMedia`/`wx.chooseMessageFile` 给的都是 `tmp_…` 临时路径。
页面代码早已为**显示/校验**准备了名字（相册用 friendlyImageName、聊天文件用
`chooseMessageFile` 返回的 `f.name`），但上传时没传给服务端，`orig_name` 落库即 tmp_xxx。

## 解法（api v？+ mp c29b5ce）

- **服务端**：`POST /api/files` 支持可选 form 字段 `name`，清洗（路径分隔符换 `_`、
  去控制字符、限长 120）后优先作为 `orig_name`；未传回退 multipart 文件名。
  入库与响应统一用清洗后的名字。存储扩展名仍由 magic bytes 决定，与 name 无关
  （契约见 docs/04 §上传）。
- **小程序**：`utils/api.ts uploadFile(filePath, onProgress, fileName?)` 经
  `formData: { name: fileName }` 传入；`print.ts startUpload` 把已有的 name 传下去。

## 预防

- 涉及「文件名/元数据」的需求，先查微信 API 是否支持自定义——`uploadFile` 不支持、
  `shareFileMessage` 支持，能力参差只能逐个确认（看 miniprogram-api-typings 的
  Option 接口比搜文档快）。
- 相册图片微信**根本不提供**原始文件名（隐私），别指望拿到真名，用友好名生成。
- 展示名与真实内容分离设计：服务端永远不信文件名（magic bytes 定 mime、随机名存储），
  name 只当元数据——这次扩展才不引入安全问题。
