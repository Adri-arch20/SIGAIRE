<script setup>
import { ref } from "vue";

const emit = defineEmits(["close", "success"]);

const username = ref("");
const password = ref("");
const showPassword = ref(false);
const errorMessage = ref("");

function login() {
  errorMessage.value = "";

  if (!username.value.trim() || !password.value.trim()) {
    errorMessage.value = "Ingresa tu usuario y contraseña.";
    return;
  }

  // Validación con usuario y contraseña fijos
  if (username.value.trim() === "admin" && password.value.trim() === "sigaire2026") {
    emit("success");
  } else {
    errorMessage.value = "Usuario o contraseña incorrectos.";
  }
}
</script>

<template>
  <div class="admin-login-overlay">
    <section class="admin-login-card">
      <!-- PANEL DE MARCA -->
      <aside class="admin-login-brand">
        <div class="admin-login-logo">
          <span class="admin-login-logo-badge">
            <img
              class="admin-login-logo-img"
              src="/Logo.png"
              alt="Logo SIGAIRE"
            />
          </span>
          <h1>SIGAIRE</h1>
          
        </div>

        <div class="admin-login-footer">
          <span class="admin-login-status"></span>
          Sistema SIGAIRE · Acceso al panel técnico
        </div>
      </aside>

      <!-- FORMULARIO -->
      <div class="admin-login-panel">
        <button
          class="admin-login-close"
          type="button"
          aria-label="Cerrar"
          @click="emit('close')"
        >
          ×
        </button>

        <div class="admin-login-heading">
          <div class="admin-login-icon">⚙</div>
          <h2>Acceso administrativo</h2>
          <p>Ingresa tus datos para continuar al panel técnico.</p>
        </div>

        <form class="admin-login-form" @submit.prevent="login">
          <label for="admin-user">Usuario</label>

          <div class="admin-login-input">
            <span>♙</span>
            <input
              id="admin-user"
              v-model="username"
              type="text"
              placeholder="Ingresa tu usuario"
              autocomplete="username"
              required
            />
          </div>

          <label for="admin-password">Contraseña</label>

          <div class="admin-login-input">
            <span>♙</span>
            <input
              id="admin-password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="Ingresa tu contraseña"
              autocomplete="current-password"
              required
            />

            <button
              class="show-password"
              type="button"
              @click="showPassword = !showPassword"
            >
              {{ showPassword ? "Ocultar" : "Mostrar" }}
            </button>
          </div>

          <p v-if="errorMessage" class="admin-login-error">
            {{ errorMessage }}
          </p>

          <button class="admin-login-submit" type="submit">
            Iniciar sesión
            <span>→</span>
          </button>
        </form>
      </div>
    </section>
  </div>
</template>

<style scoped>
.admin-login-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(65, 20, 50, 0.72);
  backdrop-filter: blur(8px);
}

/* Tarjeta dividida: marca a la izquierda, formulario a la derecha */
.admin-login-card {
  position: relative;
  display: grid;
  grid-template-columns: 0.9fr 1.1fr;
  width: 100%;
  max-width: 920px;
  overflow: hidden;
  border-radius: 32px;
  background: #ffffff;
  box-shadow: 0 30px 90px rgba(145, 38, 72, 0.35);
  animation: login-appear 0.25s ease;
}

/* ============ PANEL DE MARCA ============ */

.admin-login-brand {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 44px 36px 32px;
  overflow: hidden;
  background: #912648;
  color: #ffffff;
}

.admin-login-brand::before,
.admin-login-brand::after {
  content: "";
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  pointer-events: none;
}

.admin-login-brand::before {
  top: -90px;
  right: -90px;
  width: 260px;
  height: 260px;
}

.admin-login-brand::after {
  bottom: -110px;
  left: -80px;
  width: 280px;
  height: 280px;
  background: rgba(184, 50, 153, 0.28);
}

.admin-login-logo {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  flex: 1;
  flex-direction: column;
  justify-content: center;
  text-align: center;
}

.admin-login-logo-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 132px;
  height: 132px;
  margin-bottom: 22px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.22);
}

.admin-login-logo-img {
  width: 98px;
  height: 98px;
  object-fit: contain;
}

.admin-login-logo h1 {
  margin: 0;
  color: #ffffff;
  font-size: 36px;
  font-weight: 900;
  letter-spacing: 2.5px;
}

.admin-login-logo > span {
  margin-top: 12px;
  padding: 7px 16px;
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.16);
  color: #f7d6e2;
  font-size: 12px;
  font-weight: 850;
  letter-spacing: 1.5px;
}

.admin-login-footer {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding-top: 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.22);
  color: #f7d6e2;
  font-size: 13px;
  font-weight: 750;
  text-align: center;
}

.admin-login-status {
  flex-shrink: 0;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #20aa91;
  box-shadow: 0 0 0 4px rgba(32, 170, 145, 0.28);
}

/* ============ PANEL DEL FORMULARIO ============ */

.admin-login-panel {
  position: relative;
  padding: 52px 46px 40px;
  background: #ffffff;
}

.admin-login-close {
  position: absolute;
  top: 18px;
  right: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border: none;
  border-radius: 50%;
  background: #fcf1fa;
  color: #b83299;
  font-size: 28px;
  font-weight: bold;
  line-height: 1;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.admin-login-close:hover {
  background: #f5dff1;
  color: #911c79;
}

.admin-login-heading {
  margin-bottom: 28px;
  text-align: left;
}

.admin-login-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 58px;
  height: 58px;
  margin: 0 0 16px;
  border-radius: 50%;
  background: #fdf2fb;
  color: #b83299;
  font-size: 28px;
}

.admin-login-heading h2 {
  margin: 0;
  color: #351237;
  font-size: 28px;
  font-weight: 900;
  line-height: 1.2;
}

.admin-login-heading p {
  margin: 10px 0 0;
  color: #7a5c7c;
  font-size: 16px;
  line-height: 1.5;
  font-weight: 650;
}

.admin-login-form {
  display: flex;
  flex-direction: column;
}

.admin-login-form label {
  margin: 0 0 8px 6px;
  color: #351237;
  font-size: 15px;
  font-weight: 850;
}

/* Campos en forma de píldora */
.admin-login-input {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 58px;
  margin-bottom: 20px;
  padding: 0 20px 0 8px;
  border: 2px solid transparent;
  border-radius: 40px;
  background: #fcf1fa;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}

.admin-login-input:focus-within {
  border-color: #b83299;
  background: #ffffff;
  box-shadow: 0 0 0 5px rgba(184, 50, 153, 0.12);
}

.admin-login-input > span {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 2px 8px rgba(84, 32, 77, 0.1);
  color: #b83299;
  font-size: 20px;
}

.admin-login-input input {
  width: 100%;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: #2a0c2c;
  font-size: 17px;
  font-weight: 700;
}

.admin-login-input input::placeholder {
  color: #a894a7;
}

.show-password {
  flex-shrink: 0;
  padding: 8px 0;
  border: none;
  background: transparent;
  color: #b83299;
  font-size: 15px;
  font-weight: 850;
  cursor: pointer;
}

.admin-login-error {
  margin: -6px 0 16px 6px;
  padding: 10px 16px;
  border-left: 5px solid #c7485e;
  border-radius: 12px;
  background: #fff4f5;
  color: #c7485e;
  font-size: 15px;
  font-weight: 750;
}

.admin-login-submit {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  min-height: 60px;
  margin-top: 6px;
  border: none;
  border-radius: 40px;
  background: linear-gradient(110deg, #912648, #b83299);
  color: #ffffff;
  font-size: 18px;
  font-weight: 900;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(145, 38, 72, 0.28);
  transition: transform 0.2s, box-shadow 0.2s;
}

.admin-login-submit:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 26px rgba(145, 38, 72, 0.38);
}

.admin-login-submit span {
  font-size: 22px;
}

@keyframes login-appear {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.98);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* ============ RESPONSIVE ============ */

@media (max-width: 760px) {
  .admin-login-card {
    grid-template-columns: 1fr;
    max-width: 480px;
    max-height: 94vh;
    overflow-y: auto;
  }

  .admin-login-brand {
    padding: 28px 24px 20px;
  }

  .admin-login-logo-badge {
    width: 96px;
    height: 96px;
    margin-bottom: 14px;
  }

  .admin-login-logo-img {
    width: 70px;
    height: 70px;
  }

  .admin-login-logo h1 {
    font-size: 28px;
  }

  .admin-login-footer {
    display: none;
  }

  .admin-login-panel {
    padding: 30px 24px 28px;
  }

  .admin-login-close {
    top: 14px;
    right: 14px;
    background: rgba(255, 255, 255, 0.9);
  }

  .admin-login-heading h2 {
    font-size: 23px;
  }
}
</style>