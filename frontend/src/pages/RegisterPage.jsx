import { useEffect, useState } from 'react'
import { ArrowBackRounded, HowToRegOutlined } from '@mui/icons-material'
import { Alert, Box, Button, Card, CardContent, Divider, FormControl, InputLabel, MenuItem, Select, Stack, TextField, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import api, { errorMessage } from '../api/client'
import GoogleAuthButton from '../components/GoogleAuthButton'
import { SchoolLogo } from '../components/Common'
import { useAuth } from '../context/AuthContext'

const emptyForm = { first_name: '', last_name: '', email: '', employee_id: '', department_id: '', position_id: '', role: 'TEACHER', password: '', password_confirm: '' }

export default function RegisterPage() {
  const { googleAuth } = useAuth(); const [form, setForm] = useState(emptyForm); const [departments, setDepartments] = useState([]); const [positions, setPositions] = useState([])
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [success, setSuccess] = useState('')
  useEffect(() => { api.get('/auth/departments/').then(({ data }) => setDepartments(data.results || data)).catch((err) => setError(errorMessage(err))) }, [])
  useEffect(() => { api.get(`/auth/positions/?role=${form.role}`).then(({ data }) => setPositions(data.results || data)).catch((err) => setError(errorMessage(err))) }, [form.role])
  const change = (key) => (event) => setForm({ ...form, [key]: event.target.value })
  const submit = async (event) => { event.preventDefault(); setBusy(true); setError(''); try { const { data } = await api.post('/auth/register/', form); setSuccess(data.detail) } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) } }
  const googleRegister = async (credential) => {
    if (!form.employee_id || !form.department_id || !form.position_id) return setError('Employee ID, department, and position are required before registering with Google.')
    setBusy(true); setError('')
    try { const data = await googleAuth({ credential, mode: 'register', employee_id: form.employee_id, department_id: form.department_id, position_id: form.position_id, role: form.role }); setSuccess(data.detail) } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }
  return <Box minHeight="100vh" bgcolor="background.default" px={2} py={{ xs: 3, md: 6 }}>
    <Stack direction="row" alignItems="center" justifyContent="center" gap={1.2} mb={3}><SchoolLogo size={48} /><Box><Typography fontWeight={800}>Faculty eRepository</Typography><Typography variant="caption" color="text.secondary">Faculty account application</Typography></Box></Stack>
    <Card sx={{ maxWidth: 760, mx: 'auto' }}><CardContent sx={{ p: { xs: 3, sm: 5 } }}><Box width={48} height={48} borderRadius={3} bgcolor="primary.light" color="primary.dark" display="grid" sx={{ placeItems: 'center' }} mb={2}><HowToRegOutlined /></Box><Typography variant="h4">Create your account</Typography><Typography color="text.secondary" mt={.75} mb={3}>Submit your school details. The Principal will review and approve your access.</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}{success ? <><Alert severity="success" sx={{ mb: 3 }}>{success}</Alert><Button component={Link} to="/login" variant="contained" startIcon={<ArrowBackRounded />}>Return to sign in</Button></> : <Stack spacing={2.5}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}><TextField label="Employee ID" fullWidth required value={form.employee_id} onChange={change('employee_id')} /><FormControl size="small" fullWidth required><InputLabel>Department</InputLabel><Select label="Department" value={form.department_id} onChange={change('department_id')}>{departments.map((department) => <MenuItem key={department.id} value={department.id}>{department.name}</MenuItem>)}</Select></FormControl></Stack>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}><FormControl size="small" fullWidth required><InputLabel>Faculty role</InputLabel><Select label="Faculty role" value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value, position_id: '' })}><MenuItem value="TEACHER">Teacher</MenuItem><MenuItem value="MASTER_TEACHER">Master Teacher</MenuItem></Select></FormControl><FormControl size="small" fullWidth required><InputLabel>Position</InputLabel><Select label="Position" value={form.position_id} onChange={change('position_id')}>{positions.map((position) => <MenuItem key={position.id} value={position.id}>{position.name}</MenuItem>)}</Select></FormControl></Stack>
        <GoogleAuthButton onCredential={googleRegister} onError={() => setError('Google registration was cancelled or unavailable.')} text="signup_with" />
        <Divider><Typography variant="caption" color="text.secondary">OR REGISTER WITH EMAIL</Typography></Divider>
        <Box component="form" onSubmit={submit}><Stack spacing={2}><Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}><TextField label="First name" fullWidth required value={form.first_name} onChange={change('first_name')} /><TextField label="Last name" fullWidth required value={form.last_name} onChange={change('last_name')} /></Stack><TextField label="School email" type="email" fullWidth required value={form.email} onChange={change('email')} /><Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}><TextField label="Password" type="password" fullWidth required helperText="At least 8 characters" value={form.password} onChange={change('password')} /><TextField label="Confirm password" type="password" fullWidth required value={form.password_confirm} onChange={change('password_confirm')} /></Stack><Stack direction={{ xs: 'column-reverse', sm: 'row' }} justifyContent="space-between" gap={1}><Button component={Link} to="/login" startIcon={<ArrowBackRounded />}>Back to sign in</Button><Button type="submit" variant="contained" disabled={busy}>{busy ? 'Submitting…' : 'Submit registration'}</Button></Stack></Stack></Box>
      </Stack>}
    </CardContent></Card>
  </Box>
}
