document.addEventListener('alpine:init', () => {
    Alpine.data('adminData', () => ({
        currentView: 'dashboard',
        
        // Data arrays
        members: [],
        categories: [],
        tasks: [],
        selectedTaskIds: [],
        
        // Analytics
        dashboardStats: null,
        
        searchQuery: '',
        filterYear: '',
        filterMonth: '',
        filterDay: '',
        filterMemberId: '',
        filterCategoryId: '',
        
        showEditModal: false,
        editingTask: null,

        // Forms
        newTask: { 
            type: 'TASK', 
            title: '', category_id: '', assignment_type: 'ANYONE', assigned_member_id: '', 
            has_penalty: false, time_block: 'ANYTIME', value_amount: 0,
            repeat_type: 'daily', weekly_days: [], monthly_date: 1, 
            interval_days: 1, end_condition: 'count', recurrence_limit: 7
        },
        newMember: { name: '', avatar_emoji: '' },
        newCategory: { name: '', icon_emoji: '', color_code: '#FFDFD3' },
        
        // Finance Filters
        financeFilter: {
            month: new Date().getMonth() + 1,
            year: new Date().getFullYear(),
            member_id: ''
        },
        financeData: [],
        
        // Charts references
        loginChart: null,
        taskChart: null,
        memberChart: null,

        
        // WebSocket Auto-Refresh
        ws: null,
        connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.event === 'refresh') {
                        // Silently reload depending on current view
                        this.loadMasterData();
                        if (this.currentView === 'dashboard') this.loadDashboard();
                        if (this.currentView === 'finance') this.loadFinance();
                        if (this.currentView === 'tasks') this.loadAllTasks();
                    }
                } catch (e) {
                    console.error('WS Message Error:', e);
                }
            };
            
            this.ws.onclose = () => {
                // Auto reconnect after 3 seconds
                setTimeout(() => {
                    this.connectWebSocket();
                }, 3000);
            };
        },

        async init() {
            await this.loadMasterData();
            
            this.$watch('currentView', (val) => {
                if (val === 'dashboard') this.loadDashboard();
                if (val === 'finance') this.loadFinance();
                if (val === 'tasks') this.loadAllTasks();
            });
            
            this.$watch('financeFilter', () => {
                if(this.currentView === 'finance') this.loadFinance();
            }, { deep: true });
            
            this.loadDashboard();
            this.connectWebSocket();
        },

        async fetchApi(endpoint, options = {}) {
            if (options.body && !options.headers) {
                options.headers = { 'Content-Type': 'application/json' };
            }
            try {
                const response = await fetch(endpoint, options);
                if (!response.ok) throw new Error(await response.text());
                return await response.json();
            } catch (err) {
                console.error('API Error:', err);
                alert('เกิดข้อผิดพลาด: ' + err.message);
                return null;
            }
        },

        async loadMasterData() {
            this.members = await this.fetchApi('/members/') || [];
            this.categories = await this.fetchApi('/categories/') || [];
        },

        async loadAllTasks() {
            this.tasks = await this.fetchApi('/tasks/?limit=2000') || [];
        },

        async loadDashboard() {
            this.dashboardStats = await this.fetchApi('/admin/dashboard_stats?days=7');
            if (this.dashboardStats) {
                this.$nextTick(() => {
                    this.renderCharts();
                });
            }
        },
        
        async loadFinance() {
            const data = await this.fetchApi(`/admin/finance_stats?year=${this.financeFilter.year}&month=${this.financeFilter.month}&member_id=${this.financeFilter.member_id}`);
            if (data) this.financeData = data;
        },

        renderCharts() {
            const ctxLogin = document.getElementById('loginChart');
            const ctxTask = document.getElementById('taskChart');
            const ctxMember = document.getElementById('memberChart');
            
            if(!ctxLogin || !ctxTask || !ctxMember) return;
            
            // Destroy existing charts to prevent memory leaks and overlapping
            if(this.loginChart) this.loginChart.destroy();
            if(this.taskChart) this.taskChart.destroy();
            if(this.memberChart) this.memberChart.destroy();

            // 1. Daily Logins
            this.loginChart = new Chart(ctxLogin, {
                type: 'line',
                data: {
                    labels: this.dashboardStats.dates.map(d => d.substring(5,10)),
                    datasets: [{
                        label: 'จำนวนคนเข้าใช้ (คน)',
                        data: this.dashboardStats.logins,
                        borderColor: '#3B82F6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            // 2. Completed vs Pending
            this.taskChart = new Chart(ctxTask, {
                type: 'bar',
                data: {
                    labels: this.dashboardStats.dates.map(d => d.substring(5,10)),
                    datasets: [
                        {
                            label: 'ทำเสร็จ',
                            data: this.dashboardStats.tasks_completed,
                            backgroundColor: '#10B981',
                            borderRadius: 4
                        },
                        {
                            label: 'ค้าง',
                            data: this.dashboardStats.tasks_pending,
                            backgroundColor: '#EF4444',
                            borderRadius: 4
                        }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true } } }
            });

            // 3. Tasks per member (Pie)
            this.memberChart = new Chart(ctxMember, {
                type: 'doughnut',
                data: {
                    labels: this.dashboardStats.member_labels,
                    datasets: [{
                        data: this.dashboardStats.member_tasks,
                        backgroundColor: ['#F472B6', '#60A5FA', '#34D399', '#FBBF24', '#A78BFA'],
                        borderWidth: 0
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, cutout: '70%' }
            });
        },

        // --- Actions ---
        
        async addMember() {
            if(!this.newMember.name) return;
            await this.fetchApi('/members/', { method: 'POST', body: JSON.stringify(this.newMember) });
            this.newMember = { name: '', avatar_emoji: '' };
            await this.loadMasterData();
        },
        
        async deleteMember(id) {
            if(!confirm('ยืนยันลบสมาชิก?')) return;
            await this.fetchApi(`/members/${id}`, { method: 'DELETE' });
            await this.loadMasterData();
        },

        async addCategory() {
            if(!this.newCategory.name) return;
            const payload = {
                name: this.newCategory.name,
                icon_emoji: this.newCategory.icon_emoji,
                color_code: this.newCategory.color_code,
            };
            await this.fetchApi('/categories/', { method: 'POST', body: JSON.stringify(payload) });
            this.newCategory = { name: '', icon_emoji: '', color_code: '#FFDFD3' };
            await this.loadMasterData();
        },

        async deleteCategory(id) {
            if(!confirm('ยืนยันลบหมวดหมู่นี้?')) return;
            await this.fetchApi(`/categories/${id}`, { method: 'DELETE' });
            await this.loadMasterData();
        },

        async createTask() {
            if(!this.newTask.title) return;
            
            if (this.newTask.assignment_type === 'MEMBER' && !this.newTask.assigned_member_id) {
                if (this.members.length > 0) {
                    this.newTask.assigned_member_id = this.members[0].id;
                } else {
                    alert('กรุณาระบุชื่อคนทำ');
                    return;
                }
            }
            
            let cron_expression = null;
            let recurrence_interval_days = null;
            
            const is_recurring = (this.newTask.type === 'SCHEDULE' || this.newTask.type === 'HABIT');
            const is_habit = (this.newTask.type === 'HABIT');

            if (is_recurring) {
                if (this.newTask.repeat_type === 'daily') {
                    recurrence_interval_days = this.newTask.interval_days;
                } else if (this.newTask.repeat_type === 'weekly') {
                    const days = this.newTask.weekly_days.join(',');
                    if (days) cron_expression = `0 0 * * ${days}`;
                    else recurrence_interval_days = 7;
                } else if (this.newTask.repeat_type === 'monthly') {
                    cron_expression = `0 0 ${this.newTask.monthly_date} * *`;
                }
            }

            const recurrence_limit = this.newTask.end_condition === 'count' ? parseInt(this.newTask.recurrence_limit) : null;

            const payload = {
                title: this.newTask.title,
                category_id: this.newTask.category_id || null,
                assignment_type: this.newTask.assignment_type,
                assigned_member_id: this.newTask.assignment_type === 'MEMBER' ? (this.newTask.assigned_member_id || null) : null,
                due_date: new Date().toISOString().split('T')[0],
                task_type: 'MANUAL',
                is_recurring: is_recurring,
                has_penalty: this.newTask.has_penalty,
                is_habit: is_habit,
                time_block: this.newTask.time_block,
                value_amount: parseInt(this.newTask.value_amount) || 0,
                cron_expression: cron_expression,
                recurrence_interval_days: recurrence_interval_days,
                recurrence_limit: recurrence_limit
            };
            
            await this.fetchApi('/tasks/', { method: 'POST', body: JSON.stringify(payload) });
            
            this.newTask = { 
                type: 'TASK', title: '', category_id: '', assignment_type: 'ANYONE', assigned_member_id: '', 
                has_penalty: false, time_block: 'ANYTIME', value_amount: 0,
                repeat_type: 'daily', weekly_days: [], monthly_date: 1, 
                interval_days: 1, end_condition: 'count', recurrence_limit: 7
            };
            if(this.currentView === 'tasks') this.loadAllTasks();
        },

        openEditModal(task) {
            this.editingTask = {
                id: task.id,
                title: task.title,
                category_id: task.category_id || '',
                assigned_member_id: task.assigned_member_id || '',
                status: task.status,
                value_amount: task.value_amount || 0,
                note: task.note || '',
                admin_note: task.admin_note || '',
                is_reviewed: task.is_reviewed || false
            };
            this.showEditModal = true;
        },

        closeEditModal() {
            this.showEditModal = false;
            this.editingTask = null;
        },

        async saveEditTask() {
            if (!this.editingTask) return;
            const payload = {
                title: this.editingTask.title,
                category_id: this.editingTask.category_id ? parseInt(this.editingTask.category_id) : null,
                assigned_member_id: this.editingTask.assigned_member_id ? parseInt(this.editingTask.assigned_member_id) : null,
                status: this.editingTask.status,
                value_amount: parseInt(this.editingTask.value_amount) || 0,
                note: this.editingTask.note,
                admin_note: this.editingTask.admin_note,
                is_reviewed: this.editingTask.is_reviewed
            };
            
            await this.fetchApi(`/tasks/${this.editingTask.id}`, {
                method: 'PUT',
                body: JSON.stringify(payload)
            });
            
            this.closeEditModal();
            this.loadAllTasks();
        },

        async deleteTask(id) {
            if(!confirm('ยืนยันลบงานนี้ถาวร?')) return;
            await this.fetchApi(`/tasks/${id}`, { method: 'DELETE' });
            this.tasks = this.tasks.filter(t => t.id !== id);
            this.selectedTaskIds = this.selectedTaskIds.filter(tid => tid !== id);
        },

        async bulkDeleteTasks() {
            if(this.selectedTaskIds.length === 0) return;
            if(!confirm(`ยืนยันลบงานที่เลือกทั้ง ${this.selectedTaskIds.length} รายการถาวร?`)) return;
            
            // Delete sequentially or via Promise.all. Sequential is safer if many.
            for (let id of this.selectedTaskIds) {
                await this.fetchApi(`/tasks/${id}`, { method: 'DELETE' });
            }
            
            // Filter them out
            this.tasks = this.tasks.filter(t => !this.selectedTaskIds.includes(t.id));
            this.selectedTaskIds = [];
        },

        toggleAllTasks(e) {
            if (e.target.checked) {
                // Select all currently filtered tasks (up to 100 on screen, or just the whole filtered array? Let's do the top 100 on screen)
                this.selectedTaskIds = this.filteredTasks.slice(0, 100).map(t => t.id);
            } else {
                this.selectedTaskIds = [];
            }
        },
        
        get filteredTasks() {
            return this.tasks.filter(t => {
                let match = true;
                if (this.searchQuery) {
                    match = match && t.title.toLowerCase().includes(this.searchQuery.toLowerCase());
                }
                if (t.due_date) {
                    const parts = t.due_date.split('-');
                    if (this.filterYear) match = match && parts[0] === this.filterYear;
                    if (this.filterMonth) match = match && parts[1] === this.filterMonth;
                    if (this.filterDay) match = match && parts[2] === this.filterDay;
                } else {
                    if (this.filterYear || this.filterMonth || this.filterDay) match = false;
                }
                
                if (this.filterMemberId) {
                    match = match && (t.assigned_member_id == this.filterMemberId);
                }
                if (this.filterCategoryId) {
                    match = match && (t.category_id == this.filterCategoryId);
                }
                
                return match;
            });
        },

        getMember(id) {
            return this.members.find(m => m.id == id);
        },
        getCategory(id) {
            return this.categories.find(c => c.id == id);
        }
    }));
});
