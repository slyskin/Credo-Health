<script setup>
import { onMounted, ref } from "vue";

const API_BASE = "http://localhost:8000/api";

const patients = ref([]);
const selectedPatient = ref(null);

const listLoading = ref(true);
const listError = ref(null);

const detailLoading = ref(false);
const detailError = ref(null);

async function loadPatients() {
  listLoading.value = true;
  listError.value = null;
  try {
    const response = await fetch(`${API_BASE}/patients/`);
    if (!response.ok) {
      throw new Error(`Server responded with ${response.status}`);
    }
    const data = await response.json();
    patients.value = data.results ?? data;
  } catch (err) {
    listError.value = `Could not load patients: ${err.message}`;
  } finally {
    listLoading.value = false;
  }
}

async function selectPatient(patientId) {
  detailLoading.value = true;
  detailError.value = null;
  selectedPatient.value = null;
  try {
    const response = await fetch(`${API_BASE}/patients/${patientId}/`);
    if (!response.ok) {
      throw new Error(`Server responded with ${response.status}`);
    }
    selectedPatient.value = await response.json();
  } catch (err) {
    detailError.value = `Could not load patient detail: ${err.message}`;
  } finally {
    detailLoading.value = false;
  }
}

onMounted(loadPatients);
</script>

<template>
  <main>
    <h1>Migrated Patients</h1>

    <section class="layout">
      <div class="panel">
        <h2>Patients</h2>

        <p v-if="listLoading">Loading patients…</p>
        <p v-else-if="listError" class="error">
          {{ listError }}
          <button @click="loadPatients">Retry</button>
        </p>
        <p v-else-if="patients.length === 0">
          No patients migrated yet. Run the <code>migrate_fhir</code> management command.
        </p>
        <ul v-else>
          <li
            v-for="patient in patients"
            :key="patient.id"
            :class="{ selected: selectedPatient?.id === patient.id }"
            @click="selectPatient(patient.id)"
          >
            {{ patient.name || "(no name on record)" }}
            <span class="muted">— {{ patient.observation_count }} observations</span>
          </li>
        </ul>
      </div>

      <div class="panel">
        <h2>Observations</h2>

        <p v-if="detailLoading">Loading observations…</p>
        <p v-else-if="detailError" class="error">{{ detailError }}</p>
        <p v-else-if="!selectedPatient">Select a patient to see their observations.</p>
        <template v-else>
          <h3>{{ selectedPatient.name }}</h3>
          <p v-if="selectedPatient.observations.length === 0">
            No observations on record for this patient.
          </p>
          <table v-else>
            <thead>
              <tr>
                <th>Code</th>
                <th>Display</th>
                <th>Value</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="obs in selectedPatient.observations" :key="obs.id">
                <td>{{ obs.code }}</td>
                <td>{{ obs.display }}</td>
                <td>{{ obs.value }} {{ obs.unit }}</td>
                <td>{{ obs.effective_date ?? "—" }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </section>
  </main>
</template>

<style scoped>
/* Deliberately minimal — visual polish is out of scope for this exercise. */
main {
  font-family: system-ui, sans-serif;
  max-width: 900px;
  margin: 2rem auto;
  padding: 0 1rem;
}
.layout {
  display: flex;
  gap: 2rem;
}
.panel {
  flex: 1;
}
ul {
  list-style: none;
  padding: 0;
}
li {
  padding: 0.5rem;
  cursor: pointer;
  border-bottom: 1px solid #eee;
}
li:hover,
li.selected {
  background: #f0f4ff;
}
.muted {
  color: #777;
  font-size: 0.85em;
}
.error {
  color: #b00020;
}
table {
  border-collapse: collapse;
  width: 100%;
}
th,
td {
  text-align: left;
  padding: 0.4rem;
  border-bottom: 1px solid #eee;
}
</style>
