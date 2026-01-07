<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
// 引入 Delete 图标和 ElMessageBox
import { UploadFilled, Download, Document, Refresh, CopyDocument, Lock, Key, Right, DocumentCopy, Edit, Delete, Search } from '@element-plus/icons-vue' 
import { ElMessage, ElMessageBox } from 'element-plus'


// --- 新增：屏幕尺寸检测 ---
const screenWidth = ref(window.innerWidth)
const isMobile = computed(() => screenWidth.value < 768)

const handleResize = () => {
  screenWidth.value = window.innerWidth
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  // 初始化检测
  handleResize()
  // ...原有的 verify 逻辑如果是在 onMounted 里也保留...
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})


// --- 逻辑部分 ---
const baseUrl = "http://127.0.0.1:8000" 
const uploadUrl = `${baseUrl}/upload`
// const baseUrl = "" 
// const uploadUrl = `/upload`

// 状态管理
const isVerified = ref(false)
const accessCode = ref("")
const fileList = ref([])
const isLoading = ref(false)

// 进度条相关
const isUploading = ref(false)
const uploadPercentage = ref(0)
const uploadRef = ref(null)

// 文字上传相关
const activeTab = ref('file')
const textContent = ref("")
const textFilename = ref("")
const isTextUploading = ref(false)

//搜索相关
const searchKeyword = ref("") // 搜索关键词

// 针对 iOS 优化的老式复制法
const legacyCopy = (text) => {
  return new Promise((resolve) => {
    try {
      const textArea = document.createElement("textarea")
      textArea.value = text
      
      textArea.style.position = "fixed"
      textArea.style.left = "-9999px"
      textArea.style.top = "0"
      textArea.style.opacity = "0"
      
      textArea.contentEditable = true
      textArea.setAttribute("readonly", "") 
      
      document.body.appendChild(textArea)
      
      textArea.readOnly = false
      textArea.focus()
      textArea.select()
      textArea.setSelectionRange(0, 999999)
      
      const successful = document.execCommand('copy')
      
      document.body.removeChild(textArea)
      resolve(successful)
    } catch (err) {
      resolve(false)
    }
  })
}

// 智能复制函数
const copyToClipboard = async (text) => {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch (e) {
      // ignore
    }
  }
  return await legacyCopy(text)
}

// 登录验证
const handleLogin = async () => {
  if (!accessCode.value.trim()) {
    ElMessage.warning("请输入......")
    return
  }
  
  isLoading.value = true
  try {
    const res = await fetch(`${baseUrl}/verify?code=${accessCode.value}`)
    if (res.ok) {
      isVerified.value = true
      ElMessage.success(`欢迎进入：${accessCode.value}`)
      fetchFiles() 
    } else {
      ElMessage.error("错误！！")
    }
  } catch (e) {
    ElMessage.error("无法连接服务器")
  } finally {
    isLoading.value = false
  }
}

// // 获取列表
// const fetchFiles = async () => {
//   if (!isVerified.value) return 

//   try {
//     const res = await fetch(`${baseUrl}/list_files?code=${accessCode.value}`)
//     if (res.status === 403) {
//       isVerified.value = false
//       ElMessage.error("验证过期")
//       return
//     }
//     const data = await res.json()
//     fileList.value = data
//   } catch (error) {
//     ElMessage.error("连接服务器失败")
//   }
// }

// 修改 fetchFiles 函数
const fetchFiles = async () => {
  if (!isVerified.value) return 

  try {
    // [修改] URL 拼接逻辑，加入 keyword 参数
    let url = `${baseUrl}/list_files?code=${accessCode.value}`
    if (searchKeyword.value.trim()) {
      url += `&keyword=${encodeURIComponent(searchKeyword.value.trim())}`
    }

    const res = await fetch(url)
    if (res.status === 403) {
      isVerified.value = false
      ElMessage.error("验证过期")
      return
    }
    const data = await res.json()
    fileList.value = data
  } catch (error) {
    ElMessage.error("连接服务器失败")
  }
}

// 上传回调
const handleProgress = (evt) => {
  if (uploadPercentage.value === 100) return
  isUploading.value = true
  uploadPercentage.value = Math.floor(evt.percent)
}

const handleSuccess = () => {
  uploadPercentage.value = 100
  ElMessage.success("上传成功！")
  setTimeout(() => {
    isUploading.value = false
    uploadPercentage.value = 0
    if (uploadRef.value) uploadRef.value.clearFiles()
    fetchFiles()
  }, 1000)
}

const handleError = () => {
  isUploading.value = false
  uploadPercentage.value = 0
  ElMessage.error("上传失败")
}

// 文字上传
const handleTextUpload = async () => {
  const content = textContent.value.trim()
  if (!content) {
    ElMessage.warning("写点什么再上传吧？")
    return
  }
  isTextUploading.value = true
  try {
    let filename = textFilename.value.trim()
    if (!filename) {
      const safeContent = content.replace(/[\r\n\\/:*?"<>|]/g, '')
      let snippet = safeContent.substring(0, 10)
      if (!snippet) snippet = "note"
      filename = `${snippet}.txt`
    }
    if (!filename.toLowerCase().endsWith('.txt')) {
      filename += '.txt'
    }
    const blob = new Blob([textContent.value], { type: 'text/plain' })
    const file = new File([blob], filename, { type: 'text/plain' })
    const formData = new FormData()
    formData.append('file', file)
    formData.append('code', accessCode.value)
    const res = await fetch(uploadUrl, { method: 'POST', body: formData })

    if (res.ok) {
      ElMessage.success(`已保存为: ${filename}`)
      textContent.value = "" 
      textFilename.value = ""
      fetchFiles() 
    } else {
      ElMessage.error("保存失败")
    }
  } catch (e) {
    ElMessage.error("网络错误")
  } finally {
    isTextUploading.value = false
  }
}

// 下载文件
const downloadFile = (url) => {
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', '')
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// 复制链接
const copyLink = async (url) => {
  const fullUrl = url.startsWith('http') ? url : window.location.origin + url
  const success = await copyToClipboard(fullUrl)
  if (success) {
    ElMessage.success("链接已复制！")
  } else {
    showCopyDialog(fullUrl, "链接")
  }
}

// 复制内容
const copyFileContent = async (url) => {
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error("无法读取文件")
    const text = await res.text()
    const success = await copyToClipboard(text)
    if (success) {
      ElMessage.success("内容已复制！")
    } else {
      showCopyDialog(text, "文件内容")
    }
  } catch (err) {
    ElMessage.error("读取内容失败")
  }
}

// [修改] 删除文件逻辑
const deleteFile = (filename) => {
  ElMessageBox.confirm(
    `确定要永久删除 ${filename} 吗？`,
    '删除警告',
    {
      confirmButtonText: '狠心删除',
      cancelButtonText: '取消',
      type: 'warning',
    }
  )
  .then(async () => {
    try {
      // --- 关键修改在这里！---
      // 给 filename 加上 encodeURIComponent()
      // 这样 # 会变成 %23，空格变成 %20，服务器就能读懂了
      const safeName = encodeURIComponent(filename)
      
      const res = await fetch(`${baseUrl}/delete/${safeName}?code=${accessCode.value}`, {
        method: 'DELETE'
      })
      
      if (res.ok) {
        ElMessage.success("文件已删除")
        fetchFiles() 
      } else {
        // 如果后端返回错误信息，尝试读取一下
        const errData = await res.json().catch(() => ({}))
        ElMessage.error(errData.detail || "删除失败")
      }
    } catch (e) {
      ElMessage.error("网络错误")
    }
  })
  .catch(() => {
    // 用户取消
  })
}



// 兜底弹窗
const showCopyDialog = (content, title) => {
  ElMessageBox.confirm(
    content, 
    `自动复制失败，请手动复制${title}`, 
    {
      confirmButtonText: '点击复制', 
      cancelButtonText: '关闭',
      type: 'info',
      customStyle: { maxWidth: '90%' }
    }
  )
  .then(async () => {
    const retrySuccess = await legacyCopy(content)
    if (retrySuccess) ElMessage.success("复制成功！")
    else ElMessage.warning("请长按文本手动复制")
  })
  .catch(() => {})
}

// 辅助
const isTextFile = (filename) => {
  if (!filename) return false
  const ext = filename.split('.').pop().toLowerCase()
  return ['txt', 'md', 'json', 'py', 'js', 'html', 'css', 'log'].includes(ext)
}
</script>

<template>
  <div v-if="!isVerified" class="login-wrapper">
    <div class="login-box">
      <div class="login-icon">
        <el-icon :size="40" color="#409EFF"><Lock /></el-icon>
      </div>
      <h2>文件空间</h2>
      <p>只是用来传文件的...</p>
      <div class="input-group">
        <el-input 
          v-model="accessCode" 
          placeholder="请输入......" 
          size="large" 
          :prefix-icon="Key"
          @keyup.enter="handleLogin"
        />
        <el-button type="primary" size="large" :icon="Right" :loading="isLoading" @click="handleLogin">
          进入
        </el-button>
      </div>
    </div>
  </div>

  <div v-else class="common-layout">
    <el-container>
      <el-header class="header">
        <div class="header-content">
          <div class="logo">📂 群文件</div>
          <div style="display: flex; align-items: center; gap: 10px;padding-left: 8px;">
             <el-button link type="danger" @click="isVerified = false; accessCode = ''">退出</el-button>
          </div>
        </div>
      </el-header>

      <el-main class="main-content">
       
        <el-card class="upload-card" shadow="hover">
          <el-tabs v-model="activeTab" class="custom-tabs">
            
            <el-tab-pane label="文件上传" name="file">
              <el-upload
                ref="uploadRef"
                class="upload-demo"
                drag
                :action="uploadUrl"
                :data="{ code: accessCode }" 
                name="file"
                :show-file-list="false"
                :on-progress="handleProgress" 
                :on-success="handleSuccess"
                :on-error="handleError"
                multiple
              >
                <div v-if="isUploading" class="upload-progress-box">
                  <el-progress type="dashboard" :percentage="uploadPercentage" :width="120" />
                  <div class="uploading-text">正在上传中... {{ uploadPercentage }}%</div>
                </div>
                <div v-else>
                  <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                  <div class="el-upload__text">
                    <span class="pc-text">拖拽文件到这里，或 <em>点击上传</em></span>
                    <span class="mobile-text">点击上传文件</span>
                  </div>
                </div>
              </el-upload>
            </el-tab-pane>

            <el-tab-pane label="文字便签" name="text">
              <div class="text-upload-box">
                <el-input
                  v-model="textContent"
                  :rows="6"
                  type="textarea"
                  placeholder="在此写下文字..."
                  resize="none"
                />
                <div class="text-actions">
                  <el-input 
                    v-model="textFilename" 
                    placeholder="文件名 (留空则使用内容前10字)" 
                    style="max-width: 250px;"
                    :prefix-icon="Edit"
                  />
                  <el-button type="primary" :loading="isTextUploading" @click="handleTextUpload">
                    <el-icon><UploadFilled /></el-icon> 保存文字
                  </el-button>
                </div>
              </div>
            </el-tab-pane>

          </el-tabs>
        </el-card>

        <el-card class="list-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="header-title">📄 文件列表 ({{ fileList.length }})</span>
              
              <div class="header-actions">
                <el-input
                  v-model="searchKeyword"
                  placeholder="搜索文件名..."
                  class="search-input"
                  :prefix-icon="Search"
                  clearable
                  @keyup.enter="fetchFiles"
                  @clear="fetchFiles"
                >
                  <template #append>
                    <el-button :icon="Search" @click="fetchFiles" />
                  </template>
                </el-input>
                
                <el-button class="pc-refresh" link type="primary" :icon="Refresh" @click="fetchFiles">刷新</el-button>
              </div>
            </div>
          </template>
          
          <el-table 
            :data="fileList" 
            style="width: 100%" 
            size="large" 
            stripe 
            table-layout="fixed"
          >
            <el-table-column prop="name" label="文件名" min-width="200">
              <template #default="scope">
                <div class="file-name-wrapper">
                  <el-icon class="file-icon"><Document /></el-icon>
                  <span class="file-name-text">{{ scope.row.name }}</span>
                </div>
              </template>
            </el-table-column>
            
            <el-table-column prop="size" label="大小" width="85" align="center" />

            <el-table-column prop="date" label="时间" width="160" class-name="hidden-mobile" />
            
            <el-table-column 
              label="操作" 
              width="160" 
              align="center"
              :fixed="isMobile ? 'right' : false"
              class-name="actions-col"
            >
              <template #default="scope">
                <div class="action-buttons">
                  <el-button type="primary" size="small" circle :icon="Download" @click="downloadFile(scope.row.url)" title="下载"></el-button>
                  <el-button type="success" size="small" circle :icon="CopyDocument" @click="copyLink(scope.row.share_url)" title="复制链接"></el-button>
                  <el-button v-if="isTextFile(scope.row.name)" type="warning" size="small" circle :icon="DocumentCopy" @click="copyFileContent(scope.row.url)" title="复制内容"></el-button>
                  <el-button type="danger" size="small" circle :icon="Delete" @click="deleteFile(scope.row.name)" title="删除"></el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

      </el-main>
    </el-container>
  </div>
</template>

<style>
.text-upload-box {
  padding: 10px;
}
.text-actions {
  display: flex;
  justify-content: flex-end; /* 按钮靠右 */
  gap: 10px;
  margin-top: 15px;
}
/* 手机端调整文字上传布局 */
@media (max-width: 768px) {
  .text-actions {
    flex-direction: column; /* 手机上垂直排列 */
  }
  .text-actions .el-input {
    max-width: 100% !important;
  }
  .text-actions .el-button {
    width: 100%;
  }
}

.upload-progress-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px 0;
}
.uploading-text {
  margin-top: 10px;
  color: #409EFF;
  font-weight: bold;
}
/* --- ⬇️ 新增的登录界面样式 (放在最上面，不影响你的原有样式) --- */
.login-wrapper {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f5f7fa;
}
.login-box {
  width: 90%;
  max-width: 400px;
  background: white;
  padding: 40px;
  border-radius: 12px;
  text-align: center;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.login-icon {
  background: #ecf5ff;
  width: 70px;
  height: 70px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
}
.input-group {
  display: flex;
  flex-direction: column;
  gap: 15px;
  margin-top: 30px;
}
/* 全局设置 */
body { margin: 0; padding: 0; background-color: #f5f7fa; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }

/* 顶部栏 */
.header { background-color: #fff; border-bottom: 1px solid #e4e7ed; padding: 0 20px; position: sticky; top: 0; z-index: 100; }

/* 顶部内容容器：加宽到 1400px */
.header-content {
  max-width: 1400px; 
  margin: 0 auto;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center; /* 居中 */
  position: relative;
}

.logo { font-size: 20px; font-weight: bold; color: #409EFF; }

/* 主内容区域：加宽到 1400px */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
}

/* 卡片样式 */
.upload-card, .list-card { margin-bottom: 20px; border-radius: 8px; }
.card-header { 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  flex-wrap: wrap; /* 允许换行，适配手机 */
  gap: 10px;       /* 元素间距 */
}

.header-title {
  font-weight: 600;
  white-space: nowrap; /* 标题不换行 */
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1; /* 占据剩余空间 */
  justify-content: flex-end; /* 靠右对齐 */
  min-width: 200px; /* 最小宽度 */
}

/* 搜索相关 */
.search-input {
  max-width: 300px; /* PC端最大宽度 */
  width: 100%;
}

/* 文件名样式 */
.file-name-wrapper { display: flex; align-items: center; }
.file-icon { margin-right: 8px; font-size: 18px; color: #909399; }
.file-name-text { font-weight: 500; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* --- 响应式适配 --- */
.mobile-text { display: none; }
.mobile-refresh { display: none; }
.hidden-xs { display: table-cell; }
.hidden-mobile { display: table-cell; }
.btn-text { display: inline; margin-left: 2px; }

/* 手机端 (小于 768px) */
@media (max-width: 768px) {
  
  /* 1. 压缩单元格内边距，让数据展示更紧凑 */
  .el-table .el-table__cell {
    padding-left: 2px !important;
    padding-right: 2px !important;
  }

  /* 2. 针对【操作列】的特殊处理 */
  .el-table .actions-col .cell {
    padding: 0 !important;
    width: 100% !important;
    display: flex;
    justify-content: center;
  }
  
  /* 3. 【关键】给固定列添加背景色和阴影，防止滑动时文字重叠难看 */
  .el-table__fixed-right {
    background-color: #fff !important; /* 必须是不透明背景 */
    box-shadow: -2px 0 5px rgba(0,0,0,0.05) !important; /* 左侧加一点淡淡阴影，体现层次感 */
    height: 100% !important;
  }
  /* 修复 Element Plus 在某些版本下固定列背景透明的问题 */
  .el-table__fixed-right-patch {
    background-color: #fff !important;
  }

  /* 4. 按钮容器 */
  .action-buttons {
    gap: 3px;
    width: 100%;
    justify-content: space-evenly; 
  }
  .action-buttons .el-button {
    margin: 0 !important;
    /* 如果觉得按钮太大，可以取消下面这行的注释来微调按钮大小 */
    /* transform: scale(0.9); */
  }

  /* 5. 文件名 wrapper 高度 */
  .file-name-wrapper {
    height: 32px;
  }

  /* 搜索相关 */
  .card-header {
    flex-direction: column; /* 上下排列 */
    align-items: flex-start;
  }
  
  .header-actions {
    width: 100%;
    justify-content: space-between; /* 搜索框撑满 */
  }
  
  .search-input {
    max-width: 100%; /* 手机端撑满 */
  }

  /* 隐藏 PC 端的刷新按钮文字，只留图标，或者直接隐藏 */
  .pc-refresh {
    display: none; 
  }
}

/* 超窄屏手机 (小于 480px) */
@media (max-width: 480px) {
  .hidden-xs { display: none !important; } /* 隐藏大小列 */
}
.action-buttons {
  display: flex;
  align-items: center;
  justify-content: center; /* PC端默认居中 */
  gap: 8px;
}
</style>