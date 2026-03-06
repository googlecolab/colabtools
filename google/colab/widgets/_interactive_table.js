/**
 * Renders an interactive table widget.
 * @param {{model: !Object, el: !Element}} props The properties for rendering.
 *     - model: The ipywidgets model containing data and state.
 *     - el: The DOM element to render the widget into.
 */
function render({model, el}) {
  el.classList.add('custom-table-widget');

  // Local view of state.
  let state = {
    totalPages: 0,
    pageNum: 0,
    sortColumn: null,
    sortColumnIndex: 0,
    sortAscending: true
  };

  const container = document.createElement('div');
  container.className = 'table-container';
  el.appendChild(container);

  function sortData(data) {
    if (!state.sortColumn) return data;
    return [...data].sort((a, b) => {
      const valA = a[state.sortColumn];
      const valB = b[state.sortColumn];
      if (valA > valB) return state.sortAscending ? 1 : -1;
      if (valA < valB) return state.sortAscending ? -1 : 1;
      return 0;
    });
  }

  function changeSort(sortColumnIndex, sortAscending) {
    if (sortColumnIndex == state.sortColumnIndex &&
        sortAscending == state.sortAscending) {
      return;
    }

    state.sortColumn = model.get('columns')[sortColumnIndex];
    state.sortColumnIndex = sortColumnIndex;
    state.sortAscending = sortAscending;

    model.set('sort_column', state.sortColumnIndex);
    model.set('sort_ascending', state.sortAscending);
    model.save_changes();
  }

  function buildTable(pageData) {
    const table = document.createElement('table');

    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');

    const columns = model.get('columns') || [];
    columns.forEach(col => {
      const th = document.createElement('th');
      th.textContent = col;
      if (state.sortColumn === col) {
        th.textContent += state.sortAscending ? ' ▲' : ' ▼';
      }
      th.style.cursor = 'pointer';
      th.title = 'Click to sort';
      th.onclick = () => {
        // ChangeSort triggers an update, table will re-render on new data.
        if (state.sortColumn === col) {
          changeSort(state.sortColumnIndex, !state.sortAscending);
        } else {
          changeSort(columns.indexOf(col), true);
        }
      };
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    pageData.forEach(row => {
      const tr = document.createElement('tr');
      columns.forEach(col => {
        const td = document.createElement('td');
        td.textContent = row[col];
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  }

  function loadState() {
    const rows = model.get('rows') || 0;
    const pageSize = model.get('page_size') || 10;

    const totalPages = Math.ceil(rows / pageSize);
    state.totalPages = totalPages;

    if (state.pageNum < 0) state.pageNum = 0;
    if (state.pageNum >= totalPages && totalPages > 0)
      state.pageNum = totalPages - 1;

    const columns = model.get('columns') || [];
    state.sortColumnIndex = model.get('sort_column');
    state.sortColumn =
        state.sortColumnIndex !== null ? columns[state.sortColumnIndex] : null;
    state.sortDescending = model.get('sort_descending') || false;
  }

  function renderTable() {
    // Clear the existing content.
    container.innerHTML = '';
    const data = model.get('active_data');
    const columns = model.get('columns') || [];
    const pageSize = model.get('page_size') || 10;
    const rows = model.get('rows') || 0;

    const totalPages = state.totalPages;

    if (state.pageNum < 0) state.pageNum = 0;
    if (state.pageNum >= totalPages && totalPages > 0)
      state.pageNum = totalPages - 1;

    function changePage(newPage) {
      if (newPage != state.pageNum && newPage >= 0 && newPage < totalPages) {
        state.pageNum = newPage;
        model.set('page_num', newPage);
        model.save_changes();
      }
    }

    const pageData = sortData(data);
    const table = buildTable(pageData);

    container.appendChild(table);

    const controls = document.createElement('div');
    controls.className = 'controls';

    const pageControls = document.createElement('span');
    pageControls.className = 'page-controls';
    const start_index = state.pageNum * pageSize + 1;
    const end_index = Math.min(start_index + pageSize - 1, rows);
    pageControls.textContent = `${start_index}-${end_index} of ${rows}`;

    function addNavigationButton(text, disabled, destination) {
      const btn = document.createElement('button');
      btn.class = 'icon-button standard';
      btn.textContent = text;
      btn.disabled = disabled;
      btn.onclick = () => {
        changePage(destination);
      };
      pageControls.appendChild(btn);
    }

    addNavigationButton('⏮', state.pageNum === 0, 0);
    addNavigationButton('◀', state.pageNum === 0, state.pageNum - 1);
    addNavigationButton(
        '▶', state.pageNum >= totalPages - 1, state.pageNum + 1);
    addNavigationButton('⏭', state.pageNum >= totalPages - 1, totalPages - 1);

    const pageSizeSelect = document.createElement('select');
    [10, 20, 50, 100].forEach(size => {
      const option = document.createElement('option');
      option.value = size;
      option.textContent = `${size}`;
      if (size === pageSize) {
        option.selected = true;
      }
      pageSizeSelect.appendChild(option);
    });
    pageSizeSelect.onchange = (e) => {
      model.set('page_size', parseInt(e.target.value));
      model.save_changes();
    };

    const pageInfo = document.createElement('span');
    pageInfo.textContent = `${rows} rows by ${columns.length} columns`;

    const rowsInfo = document.createElement('span');
    rowsInfo.textContent = `Rows per page:`;

    controls.appendChild(pageInfo);
    controls.appendChild(rowsInfo);
    controls.appendChild(pageSizeSelect);
    controls.appendChild(pageControls);

    container.appendChild(controls);
  }

  function loadAndRender() {
    loadState();
    renderTable();
  }

  model.on('change:active_data', () => {
    state.page = 0;
    loadAndRender();
  });

  model.on('change:page_num', loadAndRender);
  model.on('change:page_size', loadAndRender);
  model.on('change:rows', loadAndRender);

  loadAndRender();
}

export default {render};