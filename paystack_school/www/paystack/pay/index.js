Vue.createApp({
  template:`
  <div class="container">
    <div class="py-5 text-center">
      <img class="d-block mx-auto mb-4" src="https://fiverr-res.cloudinary.com/images/q_auto,f_auto/gigs/93790811/original/d659bf6ae224ded386238ebc8e0a77c406ff9730/integrate-paystack-payment-gateway.png" alt="" width="300" height="120">
      <h2>Checkout</h2>
      <!-- <p class="lead">Below is an example form built entirely with Bootstrap's form controls. Each disabled form group has a validation state that can be triggered by attempting to submit the form without completing it.</p> -->
    </div>

    <div class="row">

      <div class="col-md-12 order-md-1">
        <h4 class="mb-3">Billing Information</h4>
        <form class="needs-validation" novalidate action="void();">
          <div class="row">
            <div class="col-md-6 mb-3">
              <label for="firstName">Name</label>
              <input type="text" class="form-control" id="name" placeholder="" v-model="customer" disabled>
            </div>
            <div class="col-md-6 mb-3">
              <label for="lastName">Email</label>
              <input type="text" class="form-control" id="email" placeholder="" v-model="email" disabled>

            </div>
            <div class="col-md-6 mb-12">
              <label for="lastName">Desc.</label>
              <input type="text" class="form-control" id="desc" placeholder="" v-model="description" disabled>

            </div>
            <div class="col-md-6 mb-3">
              <label for="lastName">Order ID</label>
              <input type="text" class="form-control" id="order_id" placeholder="" v-model="reference_docname" disabled>

            </div>
            <div class="col-md-6 mb-3">
              <label for="lastName">Currency</label>
              <input type="text" class="form-control" id="currency" placeholder="" v-model="currency" disabled>

            </div>
            <div class="col-md-6 mb-3">
              <label for="lastName">Amount</label>
              <input type="text" class="form-control" id="amount" placeholder="" v-model="amount" disabled>

            </div>
          </div>

          <button class="btn btn-primary btn-lg btn-block" type="button"
          id="paynow" @click="open_paystack">Pay Now</button>
        </form>
      </div>
    </div>

  </div>
  `,
  // data() {
  //   return {
  //     references: {
  //       'currency':'NGN',
  //       'description':'hello'
  //     },
  //   }
  // },
  data: () => (
    {
      amount:'',
      reference_doctype: '',
      reference_docname: null,
      currency:'',
      customer:'',
      description:'',
      email:''

  }),
  mounted(){
    // get payment data
    $(document).ready(()=>{
      this.initialize();
    })
  },
  methods: {
    initialize(){
      // get payment data from payment_id
      let queryString = window.location.search;
      let urlParams = new URLSearchParams(queryString);
      var payment_id = urlParams.get('payment_id')
      let references = {}
      frappe.call({
        method:'paystack_school.api.v1.get_payment_data',
        args:{
          'payment_id':payment_id
        },
        callback:(r)=>{
          if(r.message){
              this.customer = r.message.payer_name,
              this.payment_id = payment_id
              this.amount =r.message.total_amount,
              this.reference_docname = r.message.reference_docname,
              this.reference_doctype = r.message.reference_doctype,
              this.gateway = r.message.gateway,
              this.currency = r.message.currency,
              this.description = r.message.description,
              this.email = r.message.payer_email,
              this.payment_data = r.message
            
            
            
          }
        }
      })
      
      //alert('error', 'Invalid', 'Your payment request is invalid!__2');
    },
    open_paystack(){
      frappe.call({
        method: "paystack_school.api.v1.get_payment_request",
        type: "POST",
        args: this.payment_data,
        freeze: true,
        freeze_message: "Preparing payment",
        async: true,
        callback: function(r) {
          if(r.message.status=='Paid'){
            frappe.throw('This order has been paid.');
            window.location.href = history.back();
          } else {
            ///start paystack pop up
            res = r.message
            console.log(res)
            let href = `/orders/${res.metadata.reference_name}`
            let handler = PaystackPop.setup({
              key: res.key,
              email: res.email,
              amount: Number(res.amount),
              ref: res.metadata.payment_reference,
              currency: res.currency,
              metadata:res.metadata,
              // label: "Optional string that replaces customer email"
              onClose: function(){
                //frappe.msgprint(__("You cancelled the payment."));
                Swal.fire({
                  icon: 'info',
                  title: 'Payment Response',
                  text: 'You cancelled the payment',
                  footer: 'Redirecting...'
                })
                window.location.href = href;
              },
              callback: function(response){
                let prd = response
                let message = 'Payment complete! Reference: ' + response.reference;
                // alert(message);
                response['payment_request_name'] = res.metadata.payment_request_name
                response['gateway'] = res.metadata.gateway
                response['reference_doctype'] = res.metadata.reference_doctype
                response['reference_docname'] = res.metadata.reference_name
                //get payment_id
                let queryString = window.location.search;
                let urlParams = new URLSearchParams(queryString);
                var payment_id = urlParams.get('payment_id')
                response['payment_id'] = payment_id

                frappe.call({
                  method:'paystack_school.api.v1.verify_transaction',
                  args:{
                    payload:response,
                  },
                  callback:function(r){
                    Swal.fire({
                      icon: 'success',
                      title: 'Payment Successful',
                      text: 'Payment received and will be processed shortly',
                      footer: 'Redirecting...'
                    })
                    setTimeout(function(){
                      window.location.pathname = '/home';
                     
                      // alert("Hello");
                    }, 3000);
                  }

                  
                })
                // frappe.msgprint({
                //     title: __('Notification'),
                //     indicator: 'green',
                //     message: __('Your payment has been received and will be processed shortly.')
                // });
      
                
              }
            });
            handler.openIframe();
          }

        },
        
    });
    },
    popAlert(icon, title, message){
      Swal.fire({
        icon: icon,
        title: title,
        text: message,
      })
    }
  },  
    
   
}).mount('#app')
