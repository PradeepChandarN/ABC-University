/**
 * ABC University Academic Management System
 * Frontend Application Logic (FastAPI + DuckDB)
 */

(function () {
  'use strict';

  // State Management
  const state = {
    currentTable: 'DEPARTMENT',
    tablesMeta: {},
    lookups: {},
    records: [],
    filteredRecords: [],
    searchQuery: '',
    editingRecordId: null,
    deletingRecordId: null,
    badgeCounts: {}
  };

  // Human-readable titles for tables
  const TABLE_TITLES = {
    DEPARTMENT: 'Departments',
    PROGRAM: 'Degree Programs',
    STUDENT: 'Students',
    FACULTY: 'Faculty Members',
    COURSE: 'Courses',
    ENROLLMENT: 'Course Enrollments',
    ASSESSMENT: 'Course Assessments',
    EXAMINATION_RESULT: 'Examination Results',
    ATTENDANCE: 'Student Attendance',
    SCHOLARSHIP: 'Scholarships',
    HOSTEL: 'Hostel Accommodations',
    INTERNSHIP: 'Internships',
    RESEARCH_PROJECT: 'Research Projects'
  };

  // DOM Elements
  const elements = {
    sidebar: document.getElementById('sidebar'),
    mobileMenuToggle: document.getElementById('mobile-menu-toggle'),
    navItems: document.querySelectorAll('.nav-item'),
    currentTableTitle: document.getElementById('current-table-title'),
    addRecordBtn: document.getElementById('btn-add-record'),
    addRecordBtnText: document.getElementById('add-record-btn-text'),
    refreshTableBtn: document.getElementById('btn-refresh-table'),
    recalcPerfBtn: document.getElementById('btn-recalculate-perf'),
    themeToggleBtn: document.getElementById('theme-toggle'),
    tableSearch: document.getElementById('table-search'),
    dataTable: document.getElementById('data-table'),
    tableHead: document.getElementById('table-head'),
    tableBody: document.getElementById('table-body'),
    emptyState: document.getElementById('empty-state'),
    tableCountLabel: document.getElementById('table-count-label'),
    tablePkInfo: document.getElementById('table-pk-info'),
    // Form Modal
    formModal: document.getElementById('form-modal'),
    modalTitle: document.getElementById('modal-title'),
    modalCloseBtn: document.getElementById('modal-close-btn'),
    modalCancelBtn: document.getElementById('modal-cancel-btn'),
    recordForm: document.getElementById('record-form'),
    formFieldsContainer: document.getElementById('form-fields-container'),
    modalSubmitBtn: document.getElementById('modal-submit-btn'),
    // Delete Modal
    deleteModal: document.getElementById('delete-modal'),
    deleteCloseBtn: document.getElementById('delete-close-btn'),
    deleteCancelBtn: document.getElementById('delete-cancel-btn'),
    deleteConfirmBtn: document.getElementById('delete-confirm-btn'),
    deleteRecordDetails: document.getElementById('delete-record-details'),
    // Toast Container
    toastContainer: document.getElementById('toast-container')
  };

  // =========================================================================
  // Initialization
  // =========================================================================
  async function initApp() {
    bindEventListeners();
    initTheme();
    try {
      await fetchMetadata();
      await fetchLookups();
      await fetchAllCounts();
      await loadTable(state.currentTable);
    } catch (err) {
      showToast('Error initializing application: ' + err.message, 'error');
    }
  }

  // =========================================================================
  // API Fetch Utilities
  // =========================================================================
  async function apiRequest(endpoint, options = {}) {
    try {
      const res = await fetch(endpoint, {
        headers: {
          'Content-Type': 'application/json',
          ...(options.headers || {})
        },
        ...options
      });

      const contentType = res.headers.get('content-type') || '';
      let data = {};
      if (contentType.includes('application/json')) {
        data = await res.json();
      }

      if (!res.ok) {
        const errorDetail = data.detail || data.message || `HTTP ${res.status}: ${res.statusText}`;
        throw new Error(errorDetail);
      }

      return data;
    } catch (err) {
      console.error('API Request Error:', err);
      throw err;
    }
  }

  async function fetchMetadata() {
    const data = await apiRequest('/api/tables-meta');
    state.tablesMeta = data.tables || {};
  }

  async function fetchLookups() {
    try {
      const data = await apiRequest('/api/lookups');
      state.lookups = data || {};
    } catch (e) {
      console.warn('Could not fetch lookups', e);
    }
  }

  async function fetchAllCounts() {
    for (const table of Object.keys(TABLE_TITLES)) {
      try {
        const data = await apiRequest(`/api/${table}`);
        const count = data.count || (data.records ? data.records.length : 0);
        state.badgeCounts[table] = count;
        const badgeEl = document.getElementById(`badge-${table}`);
        if (badgeEl) {
          badgeEl.textContent = count;
        }
      } catch (e) {
        // Silently handle count fetch if table is empty
      }
    }
  }

  // =========================================================================
  // Table Loading & Rendering
  // =========================================================================
  async function loadTable(tableName) {
    state.currentTable = tableName;
    state.searchQuery = '';
    if (elements.tableSearch) elements.tableSearch.value = '';

    // Update UI Titles and Active Nav
    const titleText = TABLE_TITLES[tableName] || tableName;
    elements.currentTableTitle.textContent = titleText;
    elements.addRecordBtnText.textContent = `Add ${titleText.replace(/s$/, '')}`;

    elements.navItems.forEach(item => {
      if (item.getAttribute('data-table') === tableName) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    const meta = state.tablesMeta[tableName];
    if (meta && elements.tablePkInfo) {
      elements.tablePkInfo.textContent = `Primary Key: ${meta.pk}`;
    }

    try {
      elements.tableBody.innerHTML = '<tr><td colspan="100" style="text-align: center; padding: 30px;">Loading data from DuckDB...</td></tr>';
      const data = await apiRequest(`/api/${tableName}`);
      state.records = data.records || [];
      state.filteredRecords = [...state.records];
      
      // Update badge
      state.badgeCounts[tableName] = state.records.length;
      const badgeEl = document.getElementById(`badge-${tableName}`);
      if (badgeEl) badgeEl.textContent = state.records.length;

      renderTable();
    } catch (err) {
      elements.tableBody.innerHTML = `<tr><td colspan="100" style="text-align: center; padding: 30px; color: var(--danger);">Failed to load records: ${err.message}</td></tr>`;
      showToast(`Error loading ${tableName}: ${err.message}`, 'error');
    }
  }

  function renderTable() {
    const meta = state.tablesMeta[state.currentTable];
    if (!meta) return;

    const columns = meta.columns;
    const pk = meta.pk;

    // Render Headers
    let theadHtml = '<tr>';
    columns.forEach(col => {
      theadHtml += `<th>${col.label || col.name}</th>`;
    });
    theadHtml += '<th style="text-align: right;">Actions</th>';
    theadHtml += '</tr>';
    elements.tableHead.innerHTML = theadHtml;

    // Filter records by search
    if (state.searchQuery.trim() !== '') {
      const q = state.searchQuery.toLowerCase();
      state.filteredRecords = state.records.filter(row => {
        return Object.values(row).some(val => {
          if (val === null || val === undefined) return false;
          return String(val).toLowerCase().includes(q);
        });
      });
    } else {
      state.filteredRecords = [...state.records];
    }

    // Update Count Label
    elements.tableCountLabel.textContent = `Showing ${state.filteredRecords.length} of ${state.records.length} records`;

    // Render Rows or Empty State
    if (state.filteredRecords.length === 0) {
      elements.dataTable.style.display = 'none';
      elements.emptyState.style.display = 'block';
      return;
    }

    elements.dataTable.style.display = 'table';
    elements.emptyState.style.display = 'none';

    let tbodyHtml = '';
    state.filteredRecords.forEach(row => {
      const recordId = row[pk];
      tbodyHtml += `<tr data-id="${recordId}">`;

      columns.forEach(col => {
        const val = row[col.name];
        tbodyHtml += `<td>${formatCellValue(col, val)}</td>`;
      });

      // Actions Column
      tbodyHtml += `
        <td style="text-align: right;">
          <div class="action-group" style="justify-content: flex-end;">
            <button class="btn-action edit-btn" data-id="${recordId}" title="Edit Record">
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
              <span>Edit</span>
            </button>
            <button class="btn-action delete-btn" data-id="${recordId}" title="Delete Record">
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
              <span>Delete</span>
            </button>
          </div>
        </td>
      `;

      tbodyHtml += '</tr>';
    });

    elements.tableBody.innerHTML = tbodyHtml;

    // Attach row button events
    elements.tableBody.querySelectorAll('.edit-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = parseInt(btn.getAttribute('data-id'), 10);
        openEditModal(id);
      });
    });

    elements.tableBody.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = parseInt(btn.getAttribute('data-id'), 10);
        openDeleteModal(id);
      });
    });
  }

  function formatCellValue(col, val) {
    if (val === null || val === undefined) {
      return '<span style="color: var(--text-muted); font-style: italic;">null</span>';
    }

    const valStr = String(val);

    // Badges for Status/Enum values
    if (col.choices || ['result_status', 'status', 'program_level', 'faculty_type'].includes(col.name)) {
      const lower = valStr.toLowerCase();
      let badgeClass = 'badge';
      if (lower === 'pass' || lower === 'active' || lower === 'completed') badgeClass += ' badge-pass';
      else if (lower === 'fail' || lower === 'inactive') badgeClass += ' badge-fail';
      else if (lower === 'pending' || lower === 'ongoing') badgeClass += ' badge-pending';
      else badgeClass += ` badge-${lower}`;
      return `<span class="${badgeClass}">${valStr}</span>`;
    }

    // Format Decimal Marks / Percentage / Amount
    if (col.type === 'decimal') {
      if (col.name === 'attendance_percentage') {
        return `${Number(val).toFixed(2)}%`;
      }
      if (col.name === 'amount') {
        return `₹${Number(val).toLocaleString('en-IN')}`;
      }
      return Number(val).toFixed(2);
    }

    return escapeHtml(valStr);
  }

  function escapeHtml(str) {
    return str.replace(/[&<>'"]/g, 
      tag => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;'
      }[tag] || tag)
    );
  }

  // =========================================================================
  // Modal Form Management (Add & Edit)
  // =========================================================================
  function openAddModal() {
    state.editingRecordId = null;
    const meta = state.tablesMeta[state.currentTable];
    const titleText = TABLE_TITLES[state.currentTable] || state.currentTable;
    elements.modalTitle.textContent = `Add New ${titleText.replace(/s$/, '')}`;
    elements.modalSubmitBtn.textContent = 'Create Record';

    buildFormFields(meta, null);
    elements.formModal.classList.add('active');
  }

  function openEditModal(recordId) {
    state.editingRecordId = recordId;
    const meta = state.tablesMeta[state.currentTable];
    const record = state.records.find(r => r[meta.pk] === recordId);
    if (!record) {
      showToast('Record not found.', 'error');
      return;
    }

    const titleText = TABLE_TITLES[state.currentTable] || state.currentTable;
    elements.modalTitle.textContent = `Edit ${titleText.replace(/s$/, '')} (#${recordId})`;
    elements.modalSubmitBtn.textContent = 'Save Changes';

    buildFormFields(meta, record);
    elements.formModal.classList.add('active');
  }

  function closeFormModal() {
    elements.formModal.classList.remove('active');
    elements.recordForm.reset();
    state.editingRecordId = null;
  }

  function buildFormFields(meta, record) {
    elements.formFieldsContainer.innerHTML = '';
    const isEdit = record !== null;

    meta.columns.forEach(col => {
      const colName = col.name;
      const isPk = colName === meta.pk;
      const isReadonly = col.readonly || false;
      const isRequired = col.required || false;
      const initialVal = isEdit ? record[colName] : '';

      const formGroup = document.createElement('div');
      formGroup.className = 'form-group';
      if (['project_title', 'scholarship_name', 'eligibility_criteria', 'course_name'].includes(colName)) {
        formGroup.classList.add('full-width');
      }

      // Label
      const label = document.createElement('label');
      label.className = 'form-label';
      label.setAttribute('for', `field-${colName}`);
      label.innerHTML = `${col.label || colName} ${isRequired && !isReadonly ? '<span class="required">*</span>' : ''}`;
      formGroup.appendChild(label);

      // Input Widget Construction
      let inputEl;

      // Check if column is a Foreign Key
      const fkLookup = getForeignKeyLookup(col);

      if (isReadonly) {
        inputEl = document.createElement('input');
        inputEl.type = 'text';
        inputEl.className = 'form-input';
        inputEl.id = `field-${colName}`;
        inputEl.name = colName;
        inputEl.value = initialVal !== null && initialVal !== undefined ? initialVal : '0.00 (Calculated)';
        inputEl.disabled = true;
        const hint = document.createElement('span');
        hint.className = 'form-hint';
        hint.textContent = 'Automatically computed from examination results.';
        formGroup.appendChild(inputEl);
        formGroup.appendChild(hint);
        elements.formFieldsContainer.appendChild(formGroup);
        return;
      }

      if (fkLookup && fkLookup.length > 0) {
        // Render Foreign Key Dropdown
        inputEl = document.createElement('select');
        inputEl.className = 'form-select';
        inputEl.id = `field-${colName}`;
        inputEl.name = colName;
        if (isRequired) inputEl.required = true;

        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = isRequired ? `-- Select ${col.label} --` : `-- None --`;
        inputEl.appendChild(defaultOption);

        fkLookup.forEach(item => {
          const opt = document.createElement('option');
          opt.value = item.id;
          opt.textContent = item.label;
          if (isEdit && String(initialVal) === String(item.id)) {
            opt.selected = true;
          }
          inputEl.appendChild(opt);
        });
      } else if (col.choices && col.choices.length > 0) {
        // Enum choices dropdown
        inputEl = document.createElement('select');
        inputEl.className = 'form-select';
        inputEl.id = `field-${colName}`;
        inputEl.name = colName;
        if (isRequired) inputEl.required = true;

        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = isRequired ? `-- Select ${col.label} --` : `-- None --`;
        inputEl.appendChild(defaultOption);

        col.choices.forEach(choice => {
          const opt = document.createElement('option');
          opt.value = choice;
          opt.textContent = choice;
          if (isEdit && String(initialVal) === choice) {
            opt.selected = true;
          }
          inputEl.appendChild(opt);
        });
      } else if (col.type === 'date') {
        inputEl = document.createElement('input');
        inputEl.type = 'date';
        inputEl.className = 'form-input';
        inputEl.id = `field-${colName}`;
        inputEl.name = colName;
        if (isRequired) inputEl.required = true;
        if (isEdit && initialVal) {
          inputEl.value = initialVal;
        }
      } else if (col.type === 'int') {
        inputEl = document.createElement('input');
        inputEl.type = 'number';
        inputEl.step = '1';
        if (col.min !== undefined) inputEl.min = col.min;
        if (col.max !== undefined) inputEl.max = col.max;
        inputEl.className = 'form-input';
        inputEl.id = `field-${colName}`;
        inputEl.name = colName;
        if (isRequired) inputEl.required = true;
        if (isEdit && initialVal !== undefined && initialVal !== null) {
          inputEl.value = initialVal;
        }
        if (isPk && isEdit) {
          inputEl.disabled = true;
        }
      } else if (col.type === 'decimal') {
        inputEl = document.createElement('input');
        inputEl.type = 'number';
        inputEl.step = '0.01';
        inputEl.className = 'form-input';
        inputEl.id = `field-${colName}`;
        inputEl.name = colName;
        if (isRequired) inputEl.required = true;
        if (isEdit && initialVal !== undefined && initialVal !== null) {
          inputEl.value = initialVal;
        }
      } else {
        inputEl = document.createElement('input');
        inputEl.type = 'text';
        inputEl.className = 'form-input';
        inputEl.id = `field-${colName}`;
        inputEl.name = colName;
        if (isRequired) inputEl.required = true;
        if (isEdit && initialVal !== undefined && initialVal !== null) {
          inputEl.value = initialVal;
        }
      }

      formGroup.appendChild(inputEl);
      elements.formFieldsContainer.appendChild(formGroup);
    });
  }

  function getForeignKeyLookup(col) {
    if (!col.fk) return null;
    if (col.fk.startsWith('DEPARTMENT')) return state.lookups.departments;
    if (col.fk.startsWith('PROGRAM')) return state.lookups.programs;
    if (col.fk.startsWith('STUDENT')) return state.lookups.students;
    if (col.fk.startsWith('FACULTY')) return state.lookups.faculty;
    if (col.fk.startsWith('COURSE')) return state.lookups.courses;
    if (col.fk.startsWith('ASSESSMENT')) return state.lookups.assessments;
    return null;
  }

  async function handleFormSubmit(e) {
    e.preventDefault();
    const meta = state.tablesMeta[state.currentTable];
    const formData = new FormData(elements.recordForm);
    const payload = {};

    meta.columns.forEach(col => {
      const colName = col.name;
      if (col.readonly) return;
      if (state.editingRecordId !== null && colName === meta.pk) return;

      const rawVal = formData.get(colName);
      if (rawVal === null || rawVal === undefined || rawVal === '') {
        payload[colName] = null;
      } else {
        if (col.type === 'int') {
          payload[colName] = parseInt(rawVal, 10);
        } else if (col.type === 'decimal') {
          payload[colName] = parseFloat(rawVal);
        } else {
          payload[colName] = rawVal.trim();
        }
      }
    });

    elements.modalSubmitBtn.disabled = true;
    elements.modalSubmitBtn.textContent = 'Saving...';

    try {
      if (state.editingRecordId !== null) {
        // PUT edit
        await apiRequest(`/api/${state.currentTable}/${state.editingRecordId}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        });
        showToast(`Record #${state.editingRecordId} updated successfully in ${state.currentTable}.`, 'success');
      } else {
        // POST create
        await apiRequest(`/api/${state.currentTable}`, {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        showToast(`New record created successfully in ${state.currentTable}.`, 'success');
      }

      closeFormModal();
      await fetchLookups();
      await loadTable(state.currentTable);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      elements.modalSubmitBtn.disabled = false;
      elements.modalSubmitBtn.textContent = state.editingRecordId !== null ? 'Save Changes' : 'Create Record';
    }
  }

  // =========================================================================
  // Delete Modal Management
  // =========================================================================
  function openDeleteModal(recordId) {
    state.deletingRecordId = recordId;
    const meta = state.tablesMeta[state.currentTable];
    const record = state.records.find(r => r[meta.pk] === recordId);
    
    let info = `Table: ${state.currentTable} | ID: ${recordId}`;
    if (record) {
      const nameKey = Object.keys(record).find(k => k.endsWith('_name') || k.endsWith('_title'));
      if (nameKey) {
        info += ` | "${record[nameKey]}"`;
      }
    }
    elements.deleteRecordDetails.textContent = info;
    elements.deleteModal.classList.add('active');
  }

  function closeDeleteModal() {
    elements.deleteModal.classList.remove('active');
    state.deletingRecordId = null;
  }

  async function handleConfirmDelete() {
    if (!state.deletingRecordId) return;

    elements.deleteConfirmBtn.disabled = true;
    elements.deleteConfirmBtn.textContent = 'Deleting...';

    try {
      await apiRequest(`/api/${state.currentTable}/${state.deletingRecordId}`, {
        method: 'DELETE'
      });
      showToast(`Record #${state.deletingRecordId} deleted successfully from ${state.currentTable}.`, 'success');
      closeDeleteModal();
      await fetchLookups();
      await loadTable(state.currentTable);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      elements.deleteConfirmBtn.disabled = false;
      elements.deleteConfirmBtn.textContent = 'Delete Record';
    }
  }

  // =========================================================================
  // Toast Notifications
  // =========================================================================
  function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const iconSvg = type === 'success' 
      ? '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
      : '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';

    const titleText = type === 'success' ? 'Success' : 'Database Error';

    toast.innerHTML = `
      ${iconSvg}
      <div class="toast-content">
        <div class="toast-title">${titleText}</div>
        <div class="toast-message">${escapeHtml(message)}</div>
      </div>
    `;

    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 300);
    }, 4500);
  }

  // =========================================================================
  // Theme Management
  // =========================================================================
  function initTheme() {
    const savedTheme = localStorage.getItem('abc_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('abc_theme', next);
  }

  // =========================================================================
  // Event Listeners
  // =========================================================================
  function bindEventListeners() {
    // Navigation items
    elements.navItems.forEach(item => {
      item.addEventListener('click', () => {
        const table = item.getAttribute('data-table');
        if (table && table !== state.currentTable) {
          loadTable(table);
        }
        if (window.innerWidth <= 900) {
          elements.sidebar.classList.remove('open');
        }
      });
    });

    // Mobile Menu Toggle
    if (elements.mobileMenuToggle) {
      elements.mobileMenuToggle.addEventListener('click', () => {
        elements.sidebar.classList.toggle('open');
      });
    }

    // Search bar
    if (elements.tableSearch) {
      elements.tableSearch.addEventListener('input', (e) => {
        state.searchQuery = e.target.value;
        renderTable();
      });
    }

    // Refresh button
    if (elements.refreshTableBtn) {
      elements.refreshTableBtn.addEventListener('click', () => {
        loadTable(state.currentTable);
        fetchLookups();
        showToast(`Table ${state.currentTable} refreshed.`, 'success');
      });
    }

    // Recalculate Performance button
    if (elements.recalcPerfBtn) {
      elements.recalcPerfBtn.addEventListener('click', async () => {
        try {
          elements.recalcPerfBtn.disabled = true;
          await apiRequest('/api/recalculate-performance', { method: 'POST' });
          showToast('Student academic performance recalculated using Examination Results.', 'success');
          if (state.currentTable === 'STUDENT') {
            await loadTable('STUDENT');
          }
        } catch (err) {
          showToast(err.message, 'error');
        } finally {
          elements.recalcPerfBtn.disabled = false;
        }
      });
    }

    // Add Record button
    if (elements.addRecordBtn) {
      elements.addRecordBtn.addEventListener('click', openAddModal);
    }

    // Theme toggle
    if (elements.themeToggleBtn) {
      elements.themeToggleBtn.addEventListener('click', toggleTheme);
    }

    // Form Modal actions
    if (elements.modalCloseBtn) elements.modalCloseBtn.addEventListener('click', closeFormModal);
    if (elements.modalCancelBtn) elements.modalCancelBtn.addEventListener('click', closeFormModal);
    if (elements.recordForm) elements.recordForm.addEventListener('submit', handleFormSubmit);

    // Delete Modal actions
    if (elements.deleteCloseBtn) elements.deleteCloseBtn.addEventListener('click', closeDeleteModal);
    if (elements.deleteCancelBtn) elements.deleteCancelBtn.addEventListener('click', closeDeleteModal);
    if (elements.deleteConfirmBtn) elements.deleteConfirmBtn.addEventListener('click', handleConfirmDelete);

    // Close modals on clicking outside modal card
    window.addEventListener('click', (e) => {
      if (e.target === elements.formModal) closeFormModal();
      if (e.target === elements.deleteModal) closeDeleteModal();
    });

    // Escape key closes modals
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeFormModal();
        closeDeleteModal();
      }
    });
  }

  // Run app on DOM loaded
  document.addEventListener('DOMContentLoaded', initApp);

})();
