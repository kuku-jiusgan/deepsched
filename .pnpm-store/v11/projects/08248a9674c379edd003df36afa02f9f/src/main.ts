import { createApp } from 'vue'
import Antd from 'ant-design-vue'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import 'ant-design-vue/dist/reset.css'
import App from './App.vue'
import router from './router'
import './index.css'

dayjs.locale('zh-cn')

const app = createApp(App)
app.use(Antd)
app.use(router)
app.mount('#app')
