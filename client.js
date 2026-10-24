/**
 * dsh-sim-telemetry —— 浏览器半端（「设置 → 赛车遥测」一页）
 *
 * v4：UDP 端口可配 + Python 环境状态/一键安装
 *
 * 约定：client bundle 不是 ESM，是自注册脚本
 *   window.__ModuleLoader__.load({ id: '<package name>', factory: (require) => ({ inject, apply }) })
 */
window.__ModuleLoader__.load({
  id: 'dsh-sim-telemetry',
  factory: (require) => {
    const React = require('react')
    const h = React.createElement

    const API = '/api/sim-telemetry'

    const jget = async (p) => {
      const r = await fetch(API + p, { credentials: 'same-origin' })
      if (!r.ok) throw new Error('HTTP ' + r.status)
      return r.json()
    }
    const jpost = async (p, body) => {
      const r = await fetch(API + p, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body || {}),
      })
      if (!r.ok) throw new Error('HTTP ' + r.status)
      return r.json()
    }

    const S = {
      box: { display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 680, padding: '2px 2px 8px' },
      title: { fontSize: 15, fontWeight: 600 },
      card: {
        display: 'flex', flexDirection: 'column', gap: 8, padding: '10px 12px', borderRadius: 8,
        border: '0.5px solid var(--dsw-alias-border-l3,#cccccc)',
      },
      row: { display: 'flex', alignItems: 'center', gap: 12 },
      label: { fontSize: 13 },
      note: { fontSize: 11, lineHeight: '16px', color: 'var(--dsw-alias-label-tertiary,#9aa0a6)' },
      ok: { fontSize: 12, color: '#188038' },
      bad: { fontSize: 12, color: '#d93025' },
      warn: { fontSize: 12, color: '#b06000' },
      btn: {
        padding: '6px 14px', fontSize: 13, borderRadius: 8, cursor: 'pointer',
        border: '0.5px solid var(--dsw-alias-border-l3,#cccccc)', background: 'transparent', color: 'inherit',
      },
      primary: {
        padding: '6px 14px', fontSize: 13, borderRadius: 8, cursor: 'pointer', border: 0,
        background: '#3b82f6', color: '#fff',
      },
      num: {
        width: 90, padding: '4px 8px', fontSize: 13, borderRadius: 6,
        border: '0.5px solid var(--dsw-alias-border-l3,#cccccc)', background: 'transparent', color: 'inherit',
      },
      text: {
        flex: 1, minWidth: 180, padding: '4px 8px', fontSize: 12, borderRadius: 6,
        border: '0.5px solid var(--dsw-alias-border-l3,#cccccc)', background: 'transparent', color: 'inherit',
      },
      err: { fontSize: 12, color: '#d93025' },
    }

    const switchStyle = (on) => ({
      width: 40, height: 22, borderRadius: 11, border: 0, cursor: 'pointer', padding: 0,
      position: 'relative', background: on ? '#3b82f6' : 'rgba(128,128,128,.35)',
    })
    const knobStyle = (on) => ({
      position: 'absolute', top: 2, left: on ? 20 : 2, width: 18, height: 18,
      borderRadius: 9, background: '#fff', transition: 'left .15s',
    })

    function PythonCard({ st, busy, act }) {
      const checking = !st || st.pythonChecking
      const ok = st && st.pythonOk === true
      const failed = st && st.pythonOk === false
      const install = st && st.install

      return h('div', { style: S.card },
        h('div', { style: S.row },
          h('span', { style: S.label }, 'Python 环境'),
          h('span', { style: S.note }, '需要 3.10 或更新版本')),
        checking
          ? h('div', { style: S.note }, '正在检测 Python…')
          : ok
            ? h('div', { style: S.row },
              h('span', { style: S.ok }, `✓ Python ${st.pythonVersion} 已就绪`),
              h('span', { style: S.note }, st.python || ''),
            )
            : h('div', { style: S.row },
              h('span', { style: S.bad }, '✗ 没检测到 Python 3.10+'),
            ),
        !checking && ok && st.pillowOk === false
          ? h('div', { style: S.row },
            h('span', { style: S.warn }, '还缺 Pillow（画遥测图才需要）'),
            h('button', {
              type: 'button', style: S.btn, disabled: busy,
              onClick: () => act(() => jpost('/install-deps')),
            }, st.deps && !st.deps.done ? '安装中…' : '安装 Pillow'),
          )
          : null,
        st && st.deps && st.deps.done ? h('div', { style: S.note }, st.deps.step) : null,
        failed
          ? h('div', { style: S.row },
            h('button', {
              type: 'button', style: S.primary, disabled: busy || (install && !install.done),
              onClick: () => act(() => jpost('/install-python')),
            }, install && !install.done ? '安装中…' : '一键安装 Python 3.12'),
            h('button', {
              type: 'button', style: S.btn, disabled: busy,
              onClick: () => act(() => jget('/recheck')),
            }, '重新检测'),
            h('span', { style: S.note }, 'winget 优先，不行就下官方安装包静默装'),
          )
          : null,
        install && install.done ? h('div', { style: install.ok ? S.ok : S.bad }, install.step) : null,
        install && !install.done ? h('div', { style: S.note }, '安装进度：' + install.step) : null,
        h('div', { style: S.row },
          h('span', { style: S.label }, '指定 Python 路径'),
          h('input', {
            type: 'text', placeholder: '留空 = 自动探测',
            style: S.text,
            defaultValue: st && st.pythonPath ? st.pythonPath : '',
            onBlur: (e) => act(() => jpost('/settings', { pythonPath: String(e.target.value || '').trim() })),
          }),
        ),
        h('div', { style: S.note }, '自动探测顺序：你指定的路径 → py 启动器 → 常见安装目录 → PATH'),
      )
    }

    function Panel() {
      const [st, setSt] = React.useState(null)
      const [busy, setBusy] = React.useState(false)
      const [err, setErr] = React.useState('')

      const load = React.useCallback(async () => {
        try { setSt(await jget('/status')); setErr('') } catch (e) { setErr(String(e)) }
      }, [])

      React.useEffect(() => {
        load()
        const t = setInterval(load, 3000)
        return () => clearInterval(t)
      }, [load])

      const act = async (fn) => {
        setBusy(true)
        try { setSt(await fn()); setErr('') } catch (e) { setErr(String(e)) } finally { setBusy(false) }
      }

      const enabled = st ? st.enabled !== false : true
      const collecting = Boolean(st && st.collecting)

      return h('div', { style: S.box },
        h('div', null,
          h('div', { style: S.title }, '赛车遥测'),
          h('div', { style: S.note },
            '记录 F1 25 的 UDP 遥测（默认端口 20777，要和游戏里「设置 → Telemetry → UDP Port」一致），按需开始/停止。')),
        err ? h('div', { style: S.err }, '出错：' + err) : null,
        h('div', { style: S.row },
          h('span', { style: S.label }, '启用插件功能'),
          h('button', {
            type: 'button',
            style: switchStyle(enabled),
            disabled: busy,
            'aria-label': '启用插件功能',
            onClick: () => act(() => jpost('/settings', { enabled: !enabled })),
          }, h('span', { style: knobStyle(enabled) })),
          h('span', { style: S.note }, enabled ? '已启用' : '已关闭（工具会拒绝开始采集）')),
        h('div', { style: S.row },
          h('span', { style: S.label }, 'UDP 端口'),
          h('input', {
            type: 'number', min: 1, max: 65535, style: S.num,
            value: st ? (st.udpPort || 20777) : 20777,
            onChange: (e) => act(() => jpost('/settings', { udpPort: Number(e.target.value) || 20777 })),
          }),
          h('span', { style: S.note }, '默认 20777；游戏里改过端口就同步改这里')),
        h('div', { style: S.row },
          h('span', { style: S.label }, '默认记录时长'),
          h('input', {
            type: 'number', min: 1, max: 60, style: S.num,
            value: st ? Math.round((st.durationSec || 900) / 60) : 15,
            onChange: (e) => act(() => jpost('/settings', {
              durationSec: Math.max(1, Math.min(60, Number(e.target.value) || 1)) * 60,
            })),
          }),
          h('span', { style: S.note }, '分钟（最长 60）')),
        h('div', { style: S.row },
          h('span', { style: S.label }, '跑到第几圈自动出报告'),
          h('input', {
            type: 'number', min: 0, max: 50, style: S.num,
            value: st && st.autoReportLaps ? st.autoReportLaps : 0,
            onChange: (e) => act(() => jpost('/settings', {
              autoReportLaps: Math.max(0, Math.min(50, Number(e.target.value) || 0)),
            })),
          }),
          h('span', { style: S.note }, '圈（0 = 不自动停，跑满时长为止）')),
        h(PythonCard, { st, busy, act }),
        h('div', { style: S.row },
          collecting
            ? h('button', { type: 'button', style: S.btn, disabled: busy, onClick: () => act(() => jpost('/stop')) }, '停止记录')
            : h('button', {
              type: 'button', style: S.btn, disabled: busy,
              onClick: () => act(() => jpost('/start', { durationSec: st && st.durationSec })),
            }, '开始记录'),
          h('span', { style: S.note }, collecting ? `采集中：已 ${st.collectingSeconds} 秒（端口 ${st.udpPort}）` : '空闲')),
        h('div', { style: S.note }, '数据目录：' + (st ? st.dataDir : '—')),
        h('div', { style: S.note }, '提示：也可以在对话里让大肥鱼用 telemetry_start / telemetry_summary / telemetry_plot 这几个工具。'),
      )
    }

    return {
      inject: ['slots'],
      apply(ctx) {
        const slots = (typeof ctx.get === 'function' ? ctx.get('slots') : undefined) || ctx.slots
        if (!slots) return
        slots.inject('settings.section', () => slots.register(
          { name: 'settings.section', id: 'sim-telemetry', order: 31, label: '赛车遥测' },
          () => h(Panel),
        ))
      },
    }
  },
})
