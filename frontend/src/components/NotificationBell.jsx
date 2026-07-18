import { useCallback, useEffect, useState } from 'react'
import { DeleteOutlineRounded, DescriptionOutlined, DoneAllRounded, FolderSharedOutlined, NotificationsNoneRounded, PersonAddAltOutlined } from '@mui/icons-material'
import { Badge, Box, Button, CircularProgress, Divider, IconButton, Popover, Stack, Tooltip, Typography } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import api, { errorMessage } from '../api/client'
import { formatDate } from './Common'

const categoryIcons = {
  ACCOUNT: <PersonAddAltOutlined fontSize="small" />,
  REPOSITORY: <FolderSharedOutlined fontSize="small" />,
  DOCUMENT: <DescriptionOutlined fontSize="small" />,
}

export default function NotificationBell() {
  const navigate = useNavigate()
  const [anchor, setAnchor] = useState(null)
  const [notifications, setNotifications] = useState([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const refreshCount = useCallback(async () => {
    const { data } = await api.get('/notifications/unread-count/')
    setUnread(data.count)
  }, [])

  const loadPreview = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [{ data: inbox }, { data: count }] = await Promise.all([api.get('/notifications/'), api.get('/notifications/unread-count/')])
      setNotifications((inbox.results || inbox).slice(0, 10)); setUnread(count.count)
    } catch (err) { setError(errorMessage(err)) } finally { setLoading(false) }
  }, [])

  useEffect(() => {
    refreshCount().catch(() => {})
    const timer = window.setInterval(() => refreshCount().catch(() => {}), 30000)
    return () => window.clearInterval(timer)
  }, [refreshCount])

  const openPreview = (event) => { setAnchor(event.currentTarget); loadPreview() }
  const markRead = async (notification, followLink = false) => {
    if (!notification.is_read) {
      await api.post(`/notifications/${notification.id}/read/`)
      setNotifications((items) => items.map((item) => item.id === notification.id ? { ...item, is_read: true, read_at: new Date().toISOString() } : item))
      setUnread((count) => Math.max(count - 1, 0))
    }
    if (followLink && notification.link) { setAnchor(null); navigate(notification.link) }
  }
  const remove = async (event, notification) => {
    event.stopPropagation(); await api.delete(`/notifications/${notification.id}/`)
    setNotifications((items) => items.filter((item) => item.id !== notification.id))
    if (!notification.is_read) setUnread((count) => Math.max(count - 1, 0))
  }
  const markAllRead = async () => {
    await api.post('/notifications/mark-all-read/')
    setNotifications((items) => items.map((item) => ({ ...item, is_read: true, read_at: item.read_at || new Date().toISOString() }))); setUnread(0)
  }
  const clearAll = async () => {
    if (!window.confirm('Remove all notifications from your inbox?')) return
    await api.delete('/notifications/clear-all/'); setNotifications([]); setUnread(0)
  }

  return <>
    <Tooltip title="Notifications"><IconButton aria-label={`${unread} unread notifications`} onClick={openPreview}><Badge badgeContent={unread} max={99} color="error"><NotificationsNoneRounded /></Badge></IconButton></Tooltip>
    <Popover open={Boolean(anchor)} anchorEl={anchor} onClose={() => setAnchor(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }} slotProps={{ paper: { sx: { mt: 1, width: 390, maxWidth: 'calc(100vw - 24px)', borderRadius: 3, overflow: 'hidden' } } }}>
      <Stack direction="row" alignItems="center" px={2} py={1.5} gap={1}><Box flex={1}><Typography fontWeight={800}>Notifications</Typography><Typography variant="caption" color="text.secondary">{unread ? `${unread} unread` : 'You’re all caught up'}</Typography></Box><Tooltip title="Mark all as read"><span><IconButton size="small" disabled={!unread} onClick={markAllRead}><DoneAllRounded fontSize="small" /></IconButton></span></Tooltip><Button size="small" color="error" disabled={!notifications.length} onClick={clearAll}>Clear all</Button></Stack>
      <Divider />
      <Box maxHeight={480} overflow="auto">
        {loading ? <Box py={7} display="grid" sx={{ placeItems: 'center' }}><CircularProgress size={28} /></Box> : error ? <Stack alignItems="center" px={3} py={5} gap={1}><Typography color="error" textAlign="center" variant="body2">{error}</Typography><Button size="small" onClick={loadPreview}>Try again</Button></Stack> : notifications.length ? notifications.map((notification, index) => <Box key={notification.id}><Box role="button" tabIndex={0} onClick={() => markRead(notification, true)} onKeyDown={(event) => { if (event.key === 'Enter') markRead(notification, true) }} sx={{ display: 'flex', gap: 1.25, px: 2, py: 1.5, cursor: 'pointer', bgcolor: notification.is_read ? 'background.paper' : 'primary.light', '&:hover': { bgcolor: notification.is_read ? 'grey.50' : 'rgba(215, 239, 230, .8)' } }}><Box width={36} height={36} flex="0 0 auto" borderRadius={2} display="grid" color={notification.is_read ? 'text.secondary' : 'primary.main'} bgcolor={notification.is_read ? 'grey.100' : 'white'} sx={{ placeItems: 'center' }}>{categoryIcons[notification.category] || <NotificationsNoneRounded fontSize="small" />}</Box><Box flex={1} minWidth={0}><Stack direction="row" alignItems="center" gap={0.75}><Typography variant="body2" fontWeight={notification.is_read ? 650 : 800} noWrap flex={1}>{notification.title}</Typography>{!notification.is_read && <Box width={7} height={7} borderRadius="50%" bgcolor="primary.main" />}</Stack><Typography variant="caption" color="text.secondary" sx={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{notification.message}</Typography><Typography variant="caption" color="text.disabled" display="block" mt={0.4}>{formatDate(notification.created_at)}</Typography></Box><Stack alignSelf="center">{!notification.is_read && <Tooltip title="Mark as read"><IconButton size="small" onClick={(event) => { event.stopPropagation(); markRead(notification) }}><DoneAllRounded sx={{ fontSize: 18 }} /></IconButton></Tooltip>}<Tooltip title="Remove"><IconButton size="small" onClick={(event) => remove(event, notification)}><DeleteOutlineRounded sx={{ fontSize: 18 }} /></IconButton></Tooltip></Stack></Box>{index < notifications.length - 1 && <Divider />}</Box>) : <Stack alignItems="center" px={3} py={7} gap={1}><Box width={48} height={48} borderRadius="50%" bgcolor="grey.100" display="grid" color="text.secondary" sx={{ placeItems: 'center' }}><NotificationsNoneRounded /></Box><Typography fontWeight={750}>No notifications</Typography><Typography variant="body2" color="text.secondary" textAlign="center">Account and repository updates will appear here.</Typography></Stack>}
      </Box>
    </Popover>
  </>
}
