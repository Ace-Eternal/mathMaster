<template>
  <svg class="random-box-icon" viewBox="0 0 32 32" aria-hidden="true">
    <rect class="random-box-icon__frame" x="5" y="5" width="22" height="22" rx="5" />
    <path class="random-box-icon__arrow" d="M9 11h3.6c2.3 0 3.7 1.4 5.2 5s2.9 5 5.2 5h1.4" />
    <path class="random-box-icon__arrow" d="M9 21h3.6c1.7 0 3-0.8 4.1-2.7" />
    <path class="random-box-icon__arrow" d="M19.5 11.2c0.9-0.2 1.8-0.2 2.9-0.2h2" />
    <path class="random-box-icon__head" d="M22 8.4 24.8 11 22 13.6" />
    <path class="random-box-icon__head" d="M22 18.4 24.8 21 22 23.6" />
  </svg>
</template>

<style scoped>
.random-box-icon {
  width: 1em;
  height: 1em;
  display: block;
}

.random-box-icon__frame,
.random-box-icon__arrow,
.random-box-icon__head {
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.random-box-icon__frame {
  stroke-width: 2.25;
}

.random-box-icon__arrow,
.random-box-icon__head {
  stroke-width: 2.45;
}
</style>
