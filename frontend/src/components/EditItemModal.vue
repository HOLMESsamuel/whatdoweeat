<template>
  <div v-if="show" class="modal-overlay" @click="closeModal">
    <div class="modal-content" @click.stop>
      <h2>Edit Item</h2>
      <form @submit.prevent="saveItem">
        <div class="input-group">
          <input v-model="editedItem.name" placeholder="Item Name" required />
          <input v-model="editedItem.quantity" placeholder="Quantity" />
        </div>
        <div class="input-group-description">
          <textarea v-model="editedItem.description" placeholder="Description"></textarea>
        </div>
        <div class="modal-buttons">
          <button type="button" @click="closeModal">Cancel</button>
          <button type="submit">Save</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, watch } from 'vue';

interface GroceryItem {
  id: string;
  name: string;
  quantity?: string;
  description?: string;
}

export default defineComponent({
  name: 'EditItemModal',
  props: {
    show: {
      type: Boolean,
      required: true
    },
    item: {
      type: Object as () => GroceryItem | null,
      required: true
    }
  },
  emits: ['close', 'save'],
  setup(props, { emit }) {
    const editedItem = ref<GroceryItem>({ id: '', name: '', quantity: '', description: '' });

    watch(() => props.item, (newItem) => {
      if (newItem) {
        editedItem.value = { ...newItem };
      }
    }, { immediate: true });

    const closeModal = () => {
      emit('close');
    };

    const saveItem = () => {
      emit('save', editedItem.value);
      closeModal();
    };

    return {
      editedItem,
      closeModal,
      saveItem
    };
  }
});
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background-color: #699051;
  padding: 20px;
  border-radius: 8px;
  width: 90%;
  max-width: 500px;
  color: white;
}

.modal-content h2 {
  text-align: center;
  margin-bottom: 20px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 10px;
}

.input-group input {
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #445837;
  color: white;
}

.input-group-description {
  margin-bottom: 20px;
}

.input-group-description textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #445837;
  color: white;
  resize: none;
}

.modal-buttons {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.modal-buttons button {
  flex: 1;
  padding: 10px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  background-color: #445837;
  color: white;
}

.modal-buttons button:hover {
  background-color: #35442a;
}

@media (min-width: 768px) {
  .input-group {
    flex-direction: row;
  }
  
  .input-group input:last-child {
    flex: 0.3;
  }
}
</style> 