import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import LoginView from './LoginView.vue'
import PrimeVue from 'primevue/config'

function mountLogin() {
  setActivePinia(createPinia())
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: '/login', component: LoginView }, { path: '/', component: { template: '<div>Home</div>' } }],
  })
  return mount(LoginView, {
    global: { plugins: [createPinia(), router, PrimeVue] },
  })
}

describe('LoginView', () => {
  it('renders password input', () => {
    const wrapper = mountLogin()
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
  })

  it('renders login button', () => {
    const wrapper = mountLogin()
    const btn = wrapper.find('button')
    expect(btn.exists()).toBe(true)
    expect(btn.text().replace(/\s/g, '')).toContain('登录')
  })

  it('renders PilotStd title', () => {
    const wrapper = mountLogin()
    expect(wrapper.find('h1').text()).toBe('PilotStd')
  })
})
