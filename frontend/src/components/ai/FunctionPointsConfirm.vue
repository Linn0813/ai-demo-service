<template>
  <!-- 弹窗模式（向后兼容） -->
  <el-dialog
    v-if="!inlineMode"
    v-model="visible"
    title="功能模块确认"
    width="90%"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
  >
    <FunctionPointsContent
      :function-points="functionPoints"
      :requirement-doc="requirementDoc"
      @confirm="handleConfirm"
      @cancel="handleCancel"
    />
    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleConfirm" :loading="confirming">
        确认并生成测试用例
      </el-button>
    </template>
  </el-dialog>

  <!-- 页面内模式 -->
  <div v-else class="function-points-inline">
    <FunctionPointsContent
      :function-points="functionPoints"
      :requirement-doc="requirementDoc"
      @confirm="handleConfirm"
      @cancel="handleCancel"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import FunctionPointsContent from './FunctionPointsContent.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  functionPoints: {
    type: Array,
    default: () => []
  },
  requirementDoc: {
    type: String,
    default: ''
  },
  inlineMode: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const confirming = ref(false)

const handleConfirm = async (data) => {
  confirming.value = true
  try {
    emit('confirm', data)
  } finally {
    confirming.value = false
  }
}

const handleCancel = () => {
  emit('cancel')
}
</script>

<style scoped>
.function-points-inline {
  width: 100%;
}
</style>
