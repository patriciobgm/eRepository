import { useState } from 'react'
import { ArrowForwardRounded, LockOutlined, SchoolRounded, VisibilityOffOutlined, VisibilityOutlined } from '@mui/icons-material'
import { Alert, Box, Button, Card, CardContent, Checkbox, Divider, FormControlLabel, IconButton, InputAdornment, Stack, TextField, Typography } from '@mui/material'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../api/client'
import { Link } from 'react-router-dom'
import GoogleAuthButton from '../components/GoogleAuthButton'

export default function LoginPage() {
  const { login, googleAuth } = useAuth(); const [showPassword, setShowPassword] = useState(false); const [loading, setLoading] = useState(false); const [error, setError] = useState(''); const [needsOtp, setNeedsOtp] = useState(false)
  const [form, setForm] = useState({ email: '', password: '', otp: '' })
  const submit = async (event) => { event.preventDefault(); setLoading(true); setError(''); try { await login(form) } catch (err) { setError(errorMessage(err)); if (err.response?.data?.non_field_errors?.[0]?.requires_otp || JSON.stringify(err.response?.data).includes('requires_otp')) setNeedsOtp(true) } finally { setLoading(false) } }
  const googleLogin = async (credential) => { setLoading(true); setError(''); try { await googleAuth({ credential, mode: 'login' }) } catch (err) { setError(errorMessage(err)) } finally { setLoading(false) } }
  return <Box minHeight="100vh" display="grid" gridTemplateColumns={{ xs: '1fr', md: '1.05fr .95fr' }}>
    <Box className="login-pattern" bgcolor="primary.dark" color="white" p={{ xs: 3, md: 7 }} display={{ xs: 'none', md: 'flex' }} flexDirection="column" justifyContent="space-between">
      <Stack direction="row" alignItems="center" gap={1.5} position="relative"><Box width={48} height={48} bgcolor="secondary.main" borderRadius={3} display="grid" sx={{ placeItems: 'center' }}><SchoolRounded /></Box><Box><Typography fontWeight={800} fontSize={18}>Faculty eRepository</Typography><Typography variant="body2" sx={{ opacity: .65 }}>JSHS - Senior High School</Typography></Box></Stack>
      <Box position="relative" maxWidth={620}><Typography variant="h2" fontSize={{ md: 48, lg: 60 }} lineHeight={1.08}>School knowledge, safely kept and easily shared.</Typography><Typography mt={3} fontSize={18} sx={{ opacity: .72 }} maxWidth={530}>A secure home for teaching materials, official documents, and collaborative resources—built for your faculty.</Typography></Box>
      <Typography variant="caption" position="relative" sx={{ opacity: .5 }}>Protected access · Revision history · Accountable sharing</Typography>
    </Box>
    <Box bgcolor="background.default" display="grid" sx={{ placeItems: 'center' }} p={2}><Box width="100%" maxWidth={460}>
      <Stack direction="row" alignItems="center" gap={1.2} display={{ md: 'none' }} mb={4} justifyContent="center"><SchoolRounded color="primary" /><Typography fontWeight={800}>Faculty eRepository</Typography></Stack>
      <Card><CardContent sx={{ p: { xs: 3, sm: 5 } }}><Box width={48} height={48} borderRadius={3} bgcolor="primary.light" color="primary.dark" display="grid" sx={{ placeItems: 'center' }} mb={2}><LockOutlined /></Box><Typography variant="h4">Welcome back</Typography><Typography color="text.secondary" mt={.75} mb={3}>Sign in with your school account.</Typography>{error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Stack spacing={2}><GoogleAuthButton onCredential={googleLogin} onError={() => setError('Google sign-in was cancelled or unavailable.')} /><Divider><Typography variant="caption" color="text.secondary">OR USE EMAIL</Typography></Divider><Box component="form" onSubmit={submit}><Stack spacing={2}><TextField label="School email" type="email" autoComplete="email" required fullWidth value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /><TextField label="Password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" required fullWidth value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} InputProps={{ endAdornment: <InputAdornment position="end"><IconButton onClick={() => setShowPassword(!showPassword)} edge="end">{showPassword ? <VisibilityOffOutlined /> : <VisibilityOutlined />}</IconButton></InputAdornment> }} />{needsOtp && <TextField label="6-digit verification code" inputProps={{ inputMode: 'numeric', maxLength: 6 }} required value={form.otp} onChange={(e) => setForm({ ...form, otp: e.target.value.replace(/\D/g, '') })} />}<Stack direction="row" alignItems="center" justifyContent="space-between"><FormControlLabel control={<Checkbox size="small" />} label={<Typography variant="body2">Remember me</Typography>} /><Button component={Link} to="/forgot-password" size="small">Forgot password?</Button></Stack><Button type="submit" variant="contained" size="large" fullWidth disabled={loading} endIcon={<ArrowForwardRounded />}>{loading ? 'Signing in…' : 'Sign in'}</Button></Stack></Box></Stack>
      </CardContent></Card><Typography variant="body2" color="text.secondary" textAlign="center" mt={2.5}>Need a faculty account? <Button component={Link} to="/register" size="small">Register here</Button></Typography>
    </Box></Box>
  </Box>
}
