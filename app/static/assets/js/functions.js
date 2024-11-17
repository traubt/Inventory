  function dialog(dialog_title, dialog_body) {
      // Set the title of the modal
      $('#exampleModalLabel').text(dialog_title);

      // Set the body content of the modal
      $('#dialog_body').html(dialog_body);

      // Show the modal directly without triggering the button click
      $('#exampleModal').modal('show');
    }

    // Get the current date in yyyy-mm-dd format
function getCurrentDate() {
    const today = new Date();
    const year = today.getFullYear();
    const month = (today.getMonth() + 1).toString().padStart(2, '0'); // Add leading zero if needed
    const day = today.getDate().toString().padStart(2, '0'); // Add leading zero if needed
    return `${year}${month}${day}`;
}

function allOrderQtyZero() {
    return $('#ProductOrderTemplate').DataTable().column(8).data().toArray().every(value => value === 0)
}


