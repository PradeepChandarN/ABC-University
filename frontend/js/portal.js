/* ==========================================================================
   ABC UNIVERSITY - SHARED PORTAL UTILITIES
   ========================================================================== */

let currentUser = null;

async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me');
    if (!res.ok) {
      window.location.href = '/login';
      return null;
    }
    currentUser = await res.json();
    
    // Check must_change_password enforcement
    if (currentUser.must_change_password && !window.location.pathname.startsWith('/login')) {
      openPasswordModal(true);
    }
    return currentUser;
  } catch (err) {
    console.error('Auth check error:', err);
    window.location.href = '/login';
    return null;
  }
}

function showToast(message, type = 'info') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 200);
  }, 4000);
}

async function handleLogout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST' });
  } catch (e) {
    console.error(e);
  } finally {
    window.location.href = '/login';
  }
}

function openPasswordModal(isForced = false) {
  let modal = document.getElementById('changePasswordModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'changePasswordModal';
    modal.className = 'modal-backdrop';
    modal.innerHTML = `
      <div class="modal-content">
        <div class="modal-header">
          <h3>${isForced ? 'Mandatory Password Update' : 'Change Password'}</h3>
          ${!isForced ? '<button class="modal-close" onclick="closePasswordModal()">&times;</button>' : ''}
        </div>
        <div class="modal-body">
          ${isForced ? '<p style="color:var(--vermilion);font-size:0.85rem;margin-bottom:14px;font-weight:600;">For security, you must update your temporary password before accessing the portal.</p>' : ''}
          <form id="changePasswordForm" onsubmit="submitPasswordChange(event, ${isForced})">
            <div class="form-group">
              <label class="form-label">Current Password</label>
              <input type="password" id="currPassInput" class="form-control" required autocomplete="current-password" placeholder="Enter current password">
            </div>
            <div class="form-group">
              <label class="form-label">New Password (min. 6 characters)</label>
              <input type="password" id="newPassInput" class="form-control" required minlength="6" autocomplete="new-password" placeholder="Enter new password">
            </div>
            <div class="form-group">
              <label class="form-label">Confirm New Password</label>
              <input type="password" id="confirmPassInput" class="form-control" required minlength="6" autocomplete="new-password" placeholder="Confirm new password">
            </div>
            <div id="passwordError" style="color:var(--vermilion);font-size:0.82rem;margin-bottom:12px;display:none;"></div>
            <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px;">
              ${!isForced ? '<button type="button" class="btn btn-secondary" onclick="closePasswordModal()">Cancel</button>' : ''}
              <button type="submit" class="btn btn-primary" id="savePasswordBtn">Update Password</button>
            </div>
          </form>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  } else {
    modal.style.display = 'flex';
  }
}

function closePasswordModal() {
  const modal = document.getElementById('changePasswordModal');
  if (modal) modal.style.display = 'none';
}

async function submitPasswordChange(e, isForced) {
  e.preventDefault();
  const errDiv = document.getElementById('passwordError');
  errDiv.style.display = 'none';

  const curr = document.getElementById('currPassInput').value;
  const next = document.getElementById('newPassInput').value;
  const conf = document.getElementById('confirmPassInput').value;

  if (next !== conf) {
    errDiv.textContent = 'New passwords do not match.';
    errDiv.style.display = 'block';
    return;
  }

  const btn = document.getElementById('savePasswordBtn');
  btn.disabled = true;
  btn.textContent = 'Saving...';

  try {
    const res = await fetch('/api/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: curr, new_password: next })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Password change failed.');
    }

    showToast('Password updated successfully!', 'success');
    closePasswordModal();
    if (currentUser) currentUser.must_change_password = false;
  } catch (err) {
    errDiv.textContent = err.message;
    errDiv.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Update Password';
  }
}

function renderTopbar(containerId, activeTab = '') {
  const container = document.getElementById(containerId);
  if (!container || !currentUser) return;

  const role = currentUser.role;
  let navHtml = '';

  if (role === 'admin') {
    navHtml = `
      <div class="portal-nav-links">
        <a href="/admin" class="${activeTab === 'insights' ? 'active' : ''}">Insights</a>
        <a href="/admin/manage" class="${activeTab === 'manage' ? 'active' : ''}">Manage Records</a>
        <a href="/admin/users" class="${activeTab === 'users' ? 'active' : ''}">User Accounts</a>
      </div>
    `;
  }

  container.innerHTML = `
    <header class="portal-topbar">
      <a class="portal-brand" href="/${role}">
        <div class="brand-badge-icon">A</div>
        <div class="brand-text">
          <b>ABC University</b>
          <span>${role.toUpperCase()} PORTAL</span>
        </div>
      </a>
      ${navHtml}
      <div class="portal-user-actions">
        <div class="user-pill">
          <span>${currentUser.name || currentUser.user_id}</span>
          <span class="role-badge badge-${role}">${role}</span>
        </div>
        <button class="btn-header" onclick="openPasswordModal(false)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
          Password
        </button>
        <button class="btn-header btn-logout" onclick="handleLogout()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
          Sign Out
        </button>
      </div>
    </header>
  `;
}
