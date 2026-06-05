document.addEventListener('alpine:init', () => {
    Alpine.data('appData', () => ({
        currentView: 'board',
        days: [],
        selectedDate: '',
        tasks: [],
        completedTasks: [],
        pendingTasks: [],
        templates: [],
        members: [],
        categories: [],
        summary: {},
        financeFilter: { month: new Date().getMonth()+1, year: new Date().getFullYear(), member_id: '' },
        myDashboard: { weekly_stats: [] },
        myHabits: [],
        
        currentMember: null,
        showLoginScreen: false,
        taskFilter: "ME",
        showSharedAlert: true,
        
        newTask: { 
            type: 'TASK', // 'TASK', 'SCHEDULE', 'HABIT'
            title: '', category_id: '', assigned_member_id: '', assignment_type: 'MEMBER', 
            has_penalty: false,
            time_block: 'ANYTIME',
            value_amount: 0,
            repeat_type: 'daily', weekly_days: [], monthly_date: 1, 
            interval_days: 1, end_condition: 'count', recurrence_limit: 7
        },
        newMember: { name: '', avatar_emoji: '' },
        
        showAddTask: false,
        showAddMember: false,
        
        showAddCategory: false,
        newCategory: { name: '', icon_emoji: '', color_code: '#FFDFD3', rule: { rule_type: 'NONE' } },

        showNoteModal: false,

        // Task Details Modal Variables
        
        showPlanModal: false,
        taskToPlan: null,
        planTargetDate: null,
        planTargetTimeBlock: 'ANYTIME',
        isSubmittingPlan: false,

        openPlanModal(task) {
            this.taskToPlan = task;
            this.planTargetDate = this.selectedDate;
            this.planTargetTimeBlock = 'ANYTIME';
            this.showPlanModal = true;
        },

        async submitPlan() {
            this.isSubmittingPlan = true;
            try {
                const payload = {
                    new_date: this.planTargetDate,
                    new_time_block: this.planTargetTimeBlock,
                    member_id: this.currentMember ? this.currentMember.id : undefined
                };
                await this.fetchApi(`/tasks/${this.taskToPlan.id}/plan`, { method: 'PUT', body: JSON.stringify(payload) });
                this.showPlanModal = false;
                await this.loadTasks();
            } finally {
                this.isSubmittingPlan = false;
            }
        },
        
        async skipPlanTask() {
            this.isSubmittingPlan = true;
            try {
                const payload = { member_id: this.currentMember ? this.currentMember.id : undefined };
                await this.fetchApi(`/tasks/${this.taskToPlan.id}/skip`, { method: 'PUT', body: JSON.stringify(payload) });
                this.showPlanModal = false;
                await this.loadTasks();
            } finally {
                this.isSubmittingPlan = false;
            }
        },

        showTaskDetails: false,
        showOptionsModal: false,
        showHistoryModal: false,
        selectedTask: null,
        actionNote: '',
        actionFile: null,
        actionImagePreview: null,
        isSubmittingAction: false,

        openTaskDetails(task) {
            this.selectedTask = task;
            this.actionNote = '';
            this.actionFile = null;
            this.actionImagePreview = null;
            
            if (task.action_history && task.action_history.length > 0) {
                const historyWithNotes = [...task.action_history].reverse();
                const lastNoteEntry = historyWithNotes.find(h => h.note || h.image_url || h.image_path);
                if (lastNoteEntry) {
                    this.actionNote = lastNoteEntry.note || '';
                    this.actionImagePreview = lastNoteEntry.image_url || lastNoteEntry.image_path || null;
                }
            }
            
            this.showTaskDetails = true;
        },
        
        openOptionsModal(task) {
            this.taskToPlan = task;
            this.showOptionsModal = true;
        },
        
        openHistoryModal(task) {
            this.taskToPlan = task;
            this.showHistoryModal = true;
        },
        
        async revertOptionsTask() {
            this.isSubmittingAction = true;
            try {
                const payload = { member_id: this.currentMember ? this.currentMember.id : undefined };
                await this.fetchApi(`/tasks/${this.taskToPlan.id}/revert`, { method: 'PUT', body: JSON.stringify(payload) });
                this.showOptionsModal = false;
                await this.loadTasks();
            } finally {
                this.isSubmittingAction = false;
            }
        },

        handleActionImageSelect(event) {
            const file = event.target.files[0];
            if (!file) return;
            this.actionFile = file;
            const reader = new FileReader();
            reader.onload = (e) => {
                this.actionImagePreview = e.target.result;
            };
            reader.readAsDataURL(file);
        },

        compressImage(file) {
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = new Image();
                    img.onload = () => {
                        const canvas = document.createElement('canvas');
                        let width = img.width;
                        let height = img.height;
                        const MAX_WIDTH = 1024;
                        
                        if (width > MAX_WIDTH) {
                            height = Math.round((height * MAX_WIDTH) / width);
                            width = MAX_WIDTH;
                        }
                        
                        canvas.width = width;
                        canvas.height = height;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, width, height);
                        
                        canvas.toBlob((blob) => {
                            resolve(blob);
                        }, 'image/jpeg', 0.8);
                    };
                    img.src = e.target.result;
                };
                reader.readAsDataURL(file);
            });
        },

        async uploadActionImage(blob) {
            const formData = new FormData();
            formData.append('file', blob, 'upload.jpg');
            
            try {
                const res = await fetch('/upload/', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                return data.url;
            } catch (err) {
                console.error('Upload failed', err);
                return null;
            }
        },

        async submitTaskAction(actionType) {
            // Validation
            if (actionType === 'REVERTED' && !this.actionNote.trim()) {
                alert('กรุณาพิมพ์โน้ตเพื่อเป็นเหตุผลในการ Revert ด้วยครับ');
                return;
            }
            
            this.isSubmittingAction = true;
            
            try {
                let imageUrl = null;
                if (this.actionFile) {
                    const compressedBlob = await this.compressImage(this.actionFile);
                    imageUrl = await this.uploadActionImage(compressedBlob);
                }
                
                const payload = {
                    note: this.actionNote.trim() || undefined,
                    image_url: imageUrl || undefined,
                    member_id: this.currentMember ? this.currentMember.id : undefined
                };
                
                if (actionType === 'COMPLETED') {
                    await this.fetchApi(`/tasks/${this.selectedTask.id}/complete`, { method: 'PUT', body: JSON.stringify(payload) });
                    if(typeof confetti === 'function') confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
                } else if (actionType === 'SKIPPED') {
                    await this.fetchApi(`/tasks/${this.selectedTask.id}/skip`, { method: 'PUT', body: JSON.stringify(payload) });
                } else if (actionType === 'REVERTED') {
                    await this.fetchApi(`/tasks/${this.selectedTask.id}/revert`, { method: 'PUT', body: JSON.stringify(payload) });
                } else if (actionType === 'NOTE') {
                    // Update only note if status doesn't change
                    if (!payload.note) {
                        alert('กรุณาพิมพ์โน้ต');
                        this.isSubmittingAction = false;
                        return;
                    }
                    await this.fetchApi(`/tasks/${this.selectedTask.id}/note`, { method: 'PUT', body: JSON.stringify({ note: payload.note }) });
                }
                
                this.showTaskDetails = false;
                await this.loadTasks();
                if(this.loadSummary) await this.loadSummary();
            } finally {
                this.isSubmittingAction = false;
            }
        },

        editingTaskId: null,
        editingTaskNote: '',

        
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
                        // Silently reload data in background
                        this.loadData();
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
            this.generateDays();
            await this.loadData();
            this.connectWebSocket();
            
            const savedMemberId = localStorage.getItem('currentMemberId');
            if (savedMemberId && this.members.length > 0) {
                const found = this.members.find(m => m.id == savedMemberId);
                if (found) {
                    this.currentMember = found;
                } else {
                    this.showLoginScreen = true;
                }
            } else if (this.members.length > 0) {
                this.showLoginScreen = true;
            }
            
            this.$watch('selectedDate', () => {
                this.loadTasks();
            });
            this.$watch('currentView', (val) => {
                if (val === 'summary') this.loadSummary();
                if (val === 'profile' && this.currentMember) this.loadMyDashboard();
                if (val === 'finance') this.loadFinance();
            });
            this.$watch('financeFilter', () => {
                if(this.currentView === 'finance') this.loadFinance();
            }, { deep: true });
        },

        loginAs(member) {
            this.currentMember = member;
            localStorage.setItem('task_member_id', member.id);
            this.showLoginScreen = false;
            fetch('/members/' + member.id + '/login', { method: 'POST' }).catch(e => console.error(e));
            if (this.currentView === 'profile') this.loadMyDashboard();
        },

        openAddTaskModal() {
            this.newTask.assigned_member_id = this.currentMember ? this.currentMember.id : '';
            this.showAddTask = true;
        },

        logout() {
            this.currentMember = null;
            localStorage.removeItem('task_member_id');
            this.showLoginScreen = true;
        },

        generateDays() {
            const today = new Date();
            const moods = ['😴', '🐹', '✨', '🎉', '🔥', '🌸', '☕'];
            const names = ['อา.', 'จ.', 'อ.', 'พ.', 'พฤ.', 'ศ.', 'ส.'];
            
            for(let i = -1; i < 6; i++) {
                const d = new Date(today);
                d.setDate(today.getDate() + i);
                const isToday = i === 0;
                
                this.days.push({
                    date: d.toISOString().split('T')[0],
                    label: isToday ? 'วันนี้' : i === 1 ? 'พรุ่งนี้' : names[d.getDay()],
                    mood: moods[d.getDay()]
                });
            }
            this.selectedDate = this.days[1].date; // set to today
        },

        
        async loadSummary() {
            const data = await this.fetchApi('/summary/');
            if (data) {
                this.summary = data;
            }
        },

        async loadData() {
            await this.loadMembers();
            await this.loadCategories();
            await this.loadTasks();
            await this.loadTemplates();
            await this.loadSummary();
        },

        async fetchApi(url, options = {}) {
            try {
                const res = await fetch(url, {
                    headers: { 'Content-Type': 'application/json' },
                    ...options
                });
                return await res.json();
            } catch (err) {
                console.error("API Error:", err);
            }
        },

        async loadMembers() {
            this.members = await this.fetchApi('/members/') || [];
        },

        async loadCategories() {
            this.categories = await this.fetchApi('/categories/') || [];
        },

        async loadTasks() {
            if(!this.selectedDate) return;
            const allTasks = await this.fetchApi(`/tasks/?task_date=${this.selectedDate}`) || [];
            this.tasks = allTasks;
            this.completedTasks = allTasks.filter(t => t.status === 'Completed');
        },

        async loadTemplates() {
            this.templates = await this.fetchApi('/templates/') || [];
        },

        

        async loadMyDashboard() {
            if (!this.currentMember) return;
            this.myDashboard = await this.fetchApi(`/members/${this.currentMember.id}/dashboard`) || { weekly_stats: [] };
            
            const allTemplates = await this.fetchApi('/templates/') || [];
            this.myHabits = allTemplates.filter(t => t.is_habit && t.assigned_member_id === this.currentMember.id);
        },

        async toggleMyHabit(habit) {
            habit.is_active = !habit.is_active;
            await this.fetchApi(`/tasks/${habit.id}`, {
                method: 'PUT',
                body: JSON.stringify({ is_active: habit.is_active })
            });
        },

        

        

        get progressPercentage() {
            if (this.tasks.length === 0) return 0;
            return (this.completedTasks.length / this.tasks.length) * 100;
        },

        get myPendingCount() {
            if(!this.currentMember) return 0;
            return this.tasks.filter(t => t.status === 'Pending' && t.assignment_type === 'MEMBER' && t.assigned_member_id === this.currentMember.id).length;
        },
        get sharedPendingCount() {
            return this.tasks.filter(t => t.status === 'Pending' && (t.assignment_type === 'ANYONE' || t.assignment_type === 'UNASSIGNED')).length;
        },
        get allPendingCount() {
            return this.tasks.filter(t => t.status === 'Pending').length;
        },
        get overdueTasks() {
            let filtered = this.tasks.filter(t => t.status === 'Pending' && t.due_date < this.selectedDate);
            if (this.taskFilter === 'ME' && this.currentMember) {
                filtered = filtered.filter(t => t.assignment_type === 'MEMBER' && t.assigned_member_id === this.currentMember.id);
            } else if (this.taskFilter === 'SHARED') {
                filtered = filtered.filter(t => t.assignment_type === 'ANYONE' || t.assignment_type === 'UNASSIGNED');
            }
            return filtered;
        },
        get todayPendingTasks() {
            let filtered = this.tasks.filter(t => t.status === 'Pending' && t.due_date >= this.selectedDate);
            if (this.taskFilter === 'ME' && this.currentMember) {
                filtered = filtered.filter(t => t.assignment_type === 'MEMBER' && t.assigned_member_id === this.currentMember.id);
            } else if (this.taskFilter === 'SHARED') {
                filtered = filtered.filter(t => t.assignment_type === 'ANYONE' || t.assignment_type === 'UNASSIGNED');
            }
            return filtered;
        },
        get pendingTasks() {
            return this.todayPendingTasks;
        },

        get groupedPendingTasks() {
            const groups = {
                'MORNING': [],
                'AFTERNOON': [],
                'EVENING': [],
                'ANYTIME': []
            };
            this.pendingTasks.forEach(t => {
                if(groups[t.time_block]) groups[t.time_block].push(t);
                else groups['ANYTIME'].push(t);
            });
            return groups;
        },

        get totalFinanceAmount() {
            return this.financeTasks.reduce((sum, task) => sum + task.value_amount, 0);
        },

        getMember(id) {
            return this.members.find(m => m.id == id);
        },

        async createTask() {
            if (!this.newTask.title) return;
            
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
                assigned_member_id: this.newTask.assignment_type === 'MEMBER' ? (this.newTask.assigned_member_id || (this.currentMember ? this.currentMember.id : null)) : null,
                assignment_type: this.newTask.assignment_type,
                due_date: this.selectedDate,
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
            await this.fetchApi('/tasks/', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            this.showAddTask = false;
            this.newTask = { 
                type: 'TASK',
                title: '', category_id: '', assigned_member_id: '', assignment_type: 'MEMBER', 
                has_penalty: false, time_block: 'ANYTIME', value_amount: 0,
                repeat_type: 'daily', weekly_days: [], 
                monthly_date: 1, interval_days: 1, end_condition: 'count', recurrence_limit: 7
            };
            this.loadTasks();
            this.loadTemplates();
            this.loadSummary();
        },

        async addMember() {
            await this.fetchApi('/members/', {
                method: 'POST',
                body: JSON.stringify(this.newMember)
            });
            this.showAddMember = false;
            this.newMember = { name: '', avatar_emoji: '' };
            this.loadMembers();
        },

        async addCategory() {
            const payload = {
                name: this.newCategory.name,
                icon_emoji: this.newCategory.icon_emoji,
                color_code: this.newCategory.color_code,
            };
            if (this.newCategory.rule.rule_type !== 'NONE') {
                payload.rule = { rule_type: this.newCategory.rule.rule_type };
            }
            await this.fetchApi('/categories/', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            this.showAddCategory = false;
            this.newCategory = { name: '', icon_emoji: '', color_code: '#FFDFD3', rule: { rule_type: 'NONE' } };
            this.loadCategories();
        },

        async completeTask(taskId, event) {
            if(event) {
                const btn = event.currentTarget;
                btn.classList.add('scale-75', 'opacity-0');
            }
            confetti({
                particleCount: 100,
                spread: 70,
                origin: { y: 0.6 }
            });
            const chime = document.getElementById('chimeSound');
            if(chime) chime.play();
            
            setTimeout(async () => {
                await this.fetchApi(`/tasks/${taskId}/complete`, { method: 'PUT' });
                this.loadTasks();
                this.loadSummary();
            }, 300);
        },

        async skipTask(taskId, event) {
            if(event) {
                const btn = event.currentTarget;
                btn.closest('.bg-white').classList.add('opacity-0', '-translate-x-10', 'transition-all', 'duration-300');
            }
            setTimeout(async () => {
                await this.fetchApi(`/tasks/${taskId}/skip`, { method: 'PUT' });
                this.loadTasks();
                this.loadSummary();
            }, 300);
        },

        async deleteTask(taskId) {
            if(!confirm('คุณต้องการลบงานนี้จริงๆ หรือไม่?')) return;
            
            // Optimistic UI update
            this.pendingTasks = this.pendingTasks.filter(t => t.id !== taskId);
            this.tasks = this.tasks.filter(t => t.id !== taskId);
            this.templates = this.templates.filter(t => t.id !== taskId);

            // API Call
            await this.fetchApi(`/tasks/${taskId}`, { method: 'DELETE' });
            this.loadSummary();
        },
        
        async deleteMember(memberId) {
            if(!confirm('ลบสมาชิกคนนี้? (งานที่รับผิดชอบจะกลายเป็นไม่มีคนทำแทน)')) return;
            await this.fetchApi(`/members/${memberId}`, { method: 'DELETE' });
            if (this.currentMember && this.currentMember.id === memberId) this.logout();
            await this.loadData();
        },

        editNote(task) {
            this.editingTaskId = task.id;
            this.editingTaskNote = task.note || '';
            this.showNoteModal = true;
        },

        async saveNote() {
            const taskId = this.editingTaskId;
            const newNote = this.editingTaskNote;
            
            const updatedTask = await this.fetchApi(`/tasks/${taskId}/note`, {
                method: 'PUT',
                body: JSON.stringify({ note: newNote })
            });

            if (updatedTask) {
                const updateInList = (list) => {
                    const idx = list.findIndex(x => x.id === taskId);
                    if (idx !== -1) list[idx].note = newNote;
                };
                updateInList(this.tasks);
                updateInList(this.pendingTasks);
                updateInList(this.completedTasks);
            }

            this.showNoteModal = false;
        }
    }));
});
