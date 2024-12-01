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

async function fetchTOCShops() {
    try {
        const response = await fetch('/api/toc_shops'); // Call the Flask route
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json(); // Parse JSON response
        _shops = data; // Populate _shops with the fetched data
        console.log(_shops); // Log the updated _shops variable to the console
    } catch (error) {
        console.error('Error fetching TOC Shops:', error);
    }
}

// Fetch all products
async function fetchProducts() {
    try {
        const response = await fetch('/api/products'); // Call the Flask route
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const products = await response.json(); // Parse JSON response
        _products = products;
        console.log(_products); // Log the product data to the console
    } catch (error) {
        console.error('Error fetching products:', error);
    }
}

// Fetch all products
async function fetchOpenOrders() {
    try {
        const response = await fetch('/api/open_orders'); // Call the Flask route
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        _open_orders = await response.json(); // Parse JSON response
        console.log(_open_orders);
    } catch (error) {
        console.error('Error fetching products:', error);
    }
}

function getShopCodeByBlName(blName) {
    const shop = _shops.find(item => item.blName === blName);
    return shop ? shop.customer : null; // Return the customer or null if not found
}

// disable controls
function disableControlsPerRole(roles,userRole){
    // Pass the roles data from Flask to JavaScript as a JSON string

  console.log("Roles:", roles, userRole);

  var exclusions = "";  // To hold the exclusions list

  // Find the exclusions list for the current user's role
  roles.forEach(function(role) {
    if (role.role === userRole) {
      exclusions = role.exclusions;
    }
  });

  // If exclusions exist, disable the elements with corresponding IDs
  if (exclusions) {
    // Split the exclusions string by commas and loop through each exclusion
    var excludedIds = exclusions.split(',');

    excludedIds.forEach(function(id) {
      // Disable the element with the corresponding ID
      var element = $('#' + id);
      element.prop('disabled', true);  // This won't work for non-form elements

      // Add a 'disabled' class and make the item non-clickable
      element.css({
        'opacity': '0.5',  // Dim the item to indicate it's disabled
        'pointer-events': 'none',  // Disable any click interaction
      });

      // Optionally, you can also change the cursor to indicate it's not clickable
      element.css('cursor', 'not-allowed');

      console.log('Disabled element:', id);
    });
  }

};





